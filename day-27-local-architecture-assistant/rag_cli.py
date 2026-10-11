"""Day 28 commands for the existing assistant; no history or transcript writer."""
import argparse
import json
import os
import sys
import time

from explain import check_inputs, safe_text
import grounded_explain as grounded
import knowledge as kn
import knowledge_index as ix
from local_embeddings import DEFAULT_MODEL, embed_chunks, embed_query, embedding_profile, model_metadata
from markdown_chunks import chunk_snapshot
from ollama_client import check_model, generate, local_url, make_client, usage_metadata
from retrieval import query_text, search
from workspace import read_source
from generation_settings import settings


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("Неверные аргументы; см. --help.")


def parser():
    p = Parser(description="Локальная Knowledge + временный Kotlin Workspace (Python 3.12+).")
    commands = p.add_subparsers(dest="command", required=True)
    knowledge = commands.add_parser("knowledge").add_subparsers(dest="operation", required=True)
    for action in ("preview", "index", "status"):
        sub = knowledge.add_parser(action)
        sub.add_argument("--knowledge", help="Каталог Markdown (или LAA_KNOWLEDGE)")
        if action != "status":
            sub.add_argument("--include", action="append", help="Разрешить только эти relative .md paths")
            sub.add_argument("--exclude", action="append", help="Исключить relative file/subtree")
            sub.add_argument("--all-markdown", action="store_true", help="Сбросить selection policy")
        if action == "index":
            sub.add_argument("--yes", action="store_true", help="Принять показанный состав документов")
            sub.add_argument("--rebuild", action="store_true", help="Явно перестроить несовместимый/повреждённый index")
            sub.add_argument("--embedding-model", help="Новый index: qwen3-embedding:0.6b; иначе сохранённая модель")
            sub.add_argument("--base-url", default=os.getenv("LAA_BASE_URL", "http://127.0.0.1:11434"))
    sub = commands.add_parser("search", description="Без generation; text = literal OR terms FTS5, vector = cosine; scores несопоставимы.")
    sub.add_argument("--knowledge")
    sub.add_argument("--mode", choices=("text", "vector"), required=True)
    sub.add_argument("--query")
    sub.add_argument("--top-k", type=int, default=4)
    sub.add_argument("--base-url", default=os.getenv("LAA_BASE_URL", "http://127.0.0.1:11434"))
    sub = commands.add_parser("explain")
    sub.add_argument("--workspace", required=True)
    sub.add_argument("--file", required=True)
    sub.add_argument("--question")
    sub.add_argument("--knowledge")
    sub.add_argument("--retrieval", choices=("none", "text", "vector"), required=True)
    sub.add_argument("--top-k", type=int, default=4)
    sub.add_argument("--model", default=os.getenv("LAA_MODEL"))
    sub.add_argument("--base-url", default=os.getenv("LAA_BASE_URL", "http://127.0.0.1:11434"))
    sub.add_argument("--num-ctx", type=int, default=8192)
    sub.add_argument("--num-predict", type=int, default=2048)
    sub.add_argument("--temperature", type=float, default=0)
    sub.add_argument("--keep-alive", choices=("0", "5m"), default="0")
    return p


def knowledge_root(args):
    return kn.local_root(args.knowledge if args.knowledge is not None else os.getenv("LAA_KNOWLEDGE"))


def prompt(value, label):
    if value is not None:
        return value
    if not sys.stdin.isatty():
        raise ValueError("Без TTY укажите --question/--query.")
    print(label + ": ", end="", file=sys.stderr, flush=True)
    try:
        return input()
    except EOFError:
        raise ValueError("Ввод не получен (EOF).") from None


def show_diff(snapshot, previous):
    diff = kn.changes(snapshot, previous.hashes if previous else {})
    print(safe_text(json.dumps({"selection": snapshot.policy, **diff, "excluded": snapshot.excluded}, ensure_ascii=False, indent=2)))
    return diff


def knowledge_command(args, transport, metrics):
    root = knowledge_root(args)
    try:
        previous = ix.read(root, required=False)
    except RuntimeError:
        if args.operation != "index" or not args.rebuild:
            raise
        previous = None
    if args.operation == "status":
        if previous is None:
            raise RuntimeError("Index отсутствует; выполните knowledge index.")
        snapshot = kn.scan(root, previous.metadata["policy"])
        show_diff(snapshot, previous)
        ix.fresh(root, previous)
        print("Index актуален.")
        return
    selection = kn.policy(previous.metadata["policy"] if previous else None,
                          includes=args.include, excludes=args.exclude, all_markdown=args.all_markdown)
    snapshot = kn.scan(root, selection, explicit_includes=args.include is not None)
    diff = show_diff(snapshot, previous)
    if args.operation == "preview":
        return
    chunks = chunk_snapshot(snapshot)
    needs_approval = (previous is None or diff["added"] or diff["deleted"] or selection != previous.metadata["policy"])
    if needs_approval and not args.yes:
        if not sys.stdin.isatty():
            raise ValueError("Нужно принять состав: TTY либо --yes. Index не изменён.")
        try:
            answer = input("Индексировать показанные документы? [yes/NO] ")
        except EOFError:
            raise ValueError("Подтверждение не получено (EOF).") from None
        if answer.strip().lower() != "yes":
            raise ValueError("Индексация отменена; index не изменён.")
    model = args.embedding_model or (previous.metadata["embedding"]["model"] if previous else DEFAULT_MODEL)
    check_model(model)
    base = local_url(args.base_url)
    with make_client(transport) as client:
        profile = embedding_profile(client, base, model)
        if previous and profile != previous.metadata["embedding"] and not args.rebuild:
            raise RuntimeError("Embedding profile изменился; повторите явный index --rebuild.")
        unchanged = previous is not None and not any(diff[k] for k in ("added", "changed", "deleted"))
        if unchanged and selection == previous.metadata["policy"] and profile == previous.metadata["embedding"] and not args.rebuild:
            ix.fresh(root, previous)
            print("Index актуален: no-op, embeddings не вычислялись.")
            metrics["embedding_calls"] = 0
            return
        vectors = embed_chunks(client, base, profile, chunks)
    ix.write(root, snapshot, profile, chunks, vectors)
    metrics.update(documents=len(snapshot.sources), chunks=len(chunks), embedding_model=profile["model"], embedding_digest=profile["digest"])
    print(f"Index обновлён: {len(snapshot.sources)} documents, {len(chunks)} chunks.")


def retrieve(args, root, index, query, mode, transport):
    vector = None
    if mode == "vector":
        with make_client(transport) as client:
            vector = embed_query(client, local_url(args.base_url), index.metadata["embedding"], query)
    return search(root, index, query, mode, args.top_k, vector)


def main(argv, *, transport=None):
    started = time.perf_counter()
    metrics = {"status": "error"}
    try:
        if sys.version_info < (3, 12):
            raise ValueError("Требуется Python 3.12+.")
        args = parser().parse_args(argv)
        metrics["command"] = args.command
        if hasattr(args, "top_k") and not 1 <= args.top_k <= 10:
            raise ValueError("top-k должен быть 1..10.")
        if args.command == "knowledge":
            knowledge_command(args, transport, metrics)
        elif args.command == "search":
            query = query_text(prompt(args.query, "Query"))
            root = knowledge_root(args)
            index = ix.read(root)
            ix.fresh(root, index)
            hits = retrieve(args, root, index, query, args.mode, transport)
            for c in hits:
                print(safe_text(f"{c['rank']}. score={c['score']:.6g} [{c['source']} / {c['section']} / Markdown L{c['start_line']}-{c['end_line']}; {c['chunk_id']}]\n{c['text'][:500]}"))
            metrics.update(mode=args.mode, hits=len(hits))
        else:
            check_model(args.model)
            base = local_url(args.base_url)
            question = prompt(args.question, "Вопрос")
            check_inputs(question, args.num_ctx, args.num_predict)
            overrides = settings(args.temperature, 0 if args.keep_alive == "0" else args.keep_alive)
            root = index = None
            if args.retrieval == "none":
                if args.knowledge is not None:
                    raise ValueError("retrieval none не принимает --knowledge.")
            else:
                root = knowledge_root(args)
                kn.separate(root, args.workspace)
                index = ix.read(root)
                ix.fresh(root, index)
            source = read_source(args.workspace, args.file)
            query = query_text(question, source.name) if index is not None else None
            def pack(hits, thinking=True):
                return grounded.pack(source, question, args.model, args.retrieval, hits,
                                     args.num_ctx, args.num_predict, thinking=thinking, overrides=overrides)
            pack([])
            phase = time.perf_counter()
            hits = [] if index is None else retrieve(args, root, index, query, args.retrieval, transport)
            metrics["retrieval_seconds"] = round(time.perf_counter() - phase, 6)
            body, selected = pack(hits)
            metrics.update(retrieval=args.retrieval, selected=len(selected), omitted=len(hits) - len(selected),
                           num_ctx=args.num_ctx, num_predict=args.num_predict, **overrides,
                           seed=28, ttft_seconds="unavailable")
            with make_client(transport) as client:
                identity, shown = model_metadata(client, base, args.model, "completion")
                thinking = "thinking" in shown["capabilities"]
                metrics.update(identity, think=False if thinking else "not_supported")
                if not thinking:
                    body, selected = pack(hits, False)
                phase = time.perf_counter()
                response = generate(client, base, body)
                metrics["generation_seconds"] = round(time.perf_counter() - phase, 6)
            metrics.update(usage_metadata(response))
            result = grounded.parse(response, len(source.lines), grounded.status(args.retrieval, selected), selected)
            print(grounded.render(result, selected))
        metrics["status"] = "completed"
        return 0
    except KeyboardInterrupt:
        print("Операция отменена.", file=sys.stderr)
        return 130
    except ValueError as error:
        print("Ошибка ввода: " + str(error), file=sys.stderr)
        return 2
    except OSError:
        print("Ошибка файловой операции/вывода; содержимое не записывалось в отчёт.", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print("Ошибка: " + str(error), file=sys.stderr)
        return 1
    finally:
        metrics["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        print(json.dumps(metrics, ensure_ascii=True), file=sys.stderr)

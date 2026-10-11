"""One-shot local Kotlin assistant. No persistence, subprocesses, or backend imports."""
import sys

# Do not create import caches when running the CLI.
sys.dont_write_bytecode = True

import argparse
import json
import os
import time

from explain import check_inputs, parse_explanation, render, request_bytes
from ollama_client import check_model, generate, local_url, make_client, supports_thinking, usage_metadata
from workspace import read_source


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's original message can include a question or other private input.
        raise ValueError("Неверные аргументы командной строки; см. --help.")


def parser():
    p = Parser(description="Объяснение одного Kotlin-файла через локальную Ollama (Python 3.12+).")
    p.add_argument("--workspace", required=True, help="Разрешённый локальный каталог")
    p.add_argument("--file", required=True, help="Путь .kt относительно Workspace")
    p.add_argument("--question", help="Без флага: один вопрос из интерактивного терминала")
    p.add_argument("--model", default=os.getenv("LAA_MODEL"), help="Установленная локальная модель (или LAA_MODEL)")
    p.add_argument("--base-url", default=os.getenv("LAA_BASE_URL", "http://127.0.0.1:11434"))
    p.add_argument("--num-ctx", type=int, default=8192)
    p.add_argument("--num-predict", type=int, default=2048)
    return p


def main(argv=None, *, transport=None):
    started = time.perf_counter()
    metrics = None
    try:
        if sys.version_info < (3, 12):
            raise ValueError("Требуется Python 3.12 или новее.")
        args = parser().parse_args(argv)
        check_model(args.model)
        base_url = local_url(args.base_url)
        question = args.question
        if question is None:
            if not sys.stdin.isatty():
                raise ValueError("Без интерактивного терминала укажите --question.")
            print("Вопрос: ", end="", file=sys.stderr, flush=True)
            try:
                question = input()
            except EOFError:
                raise ValueError("Вопрос не введён (EOF).") from None
        check_inputs(question, args.num_ctx, args.num_predict)
        source = read_source(args.workspace, args.file)
        # Reject an oversized request before even metadata HTTP; think:false is
        # the larger of the two possible payloads.
        body = request_bytes(source, question, args.model, args.num_ctx, args.num_predict, thinking=True)
        metrics = {"model": args.model, "num_ctx": args.num_ctx, "num_predict": args.num_predict,
                   "status": "error", "think": "unavailable", **usage_metadata({})}
        with make_client(transport) as client:
            thinking = supports_thinking(client, base_url, args.model)
            metrics["think"] = False if thinking else "not_supported"
            if not thinking:
                body = request_bytes(source, question, args.model, args.num_ctx, args.num_predict, thinking=False)
            response = generate(client, base_url, body)
        metrics.update(usage_metadata(response))
        explanation = parse_explanation(response, len(source.lines))
        print(render(explanation))
        metrics["status"] = "completed"
        return 0
    except KeyboardInterrupt:
        print("Операция отменена пользователем.", file=sys.stderr)
        return 130
    except ValueError as error:
        # All input errors above use our own content-free messages.
        print(f"Ошибка ввода: {error}", file=sys.stderr)
        return 2
    except OSError:
        print("Ошибка чтения Workspace или вывода в терминал.", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    finally:
        if metrics is not None:
            metrics["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            print(json.dumps(metrics, ensure_ascii=True), file=sys.stderr)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())

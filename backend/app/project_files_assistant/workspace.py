"""Manifest-bound copies, deterministic literal search and observed evidence."""
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from . import (ROOT, DAY, SOURCES, TARGET, MAX_FILE, MAX_TOTAL, MAX_RESULT,
               bounded, canonical, clean_text, digest, guard, name, read_json,
               require, write_json)


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    require(result.returncode == 0, "git_snapshot_unavailable")
    return result.stdout.decode("utf-8").strip()


def prepare(scenario, *, root=ROOT, run_dir=None):
    root = guard(root)
    manifest = read_json(guard(root / DAY / "manifest.json", root))
    require(manifest.get("version") == 1 and
            tuple(s["path"] for s in manifest["sources"]) == SOURCES, "invalid_manifest")
    goals = read_json(guard(root / DAY / "scenarios.json", root))
    require(scenario in {"A", "B"}, "unknown_scenario")
    spec = goals[scenario]
    revision = git(root, "rev-parse", "HEAD")
    require(not git(root, "diff", "--name-only", "HEAD", "--", *SOURCES), "dirty_sources")
    snapshots, hashes, total = {}, {}, 0
    for entry in manifest["sources"]:
        path = name(entry["path"])
        raw = bounded(guard(root / path, root))
        clean_text(raw.decode("utf-8-sig"))
        require(digest(raw) == entry["sha256"], "manifest_hash_mismatch")
        snapshots[path], hashes[path] = raw, digest(raw)
        total += len(raw)
    require(total <= MAX_TOTAL, "corpus_size_limit")
    if scenario == "B":
        snapshots[TARGET] = bounded(guard(root / DAY / "fixtures/search-outdated.md", root))
    run = guard(run_dir or root / "backend/.local/day34/runs" / str(uuid4()))
    require(not run.exists(), "run_exists")
    run.mkdir(parents=True)
    workspace = guard(run / "workspace", run)
    workspace.mkdir()
    for path, raw in snapshots.items():
        dest = guard(workspace / path, workspace)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(raw)
    (workspace / "docs").mkdir(exist_ok=True)
    meta = dict(version=1, run_id=run.name, origin=str(root), revision=revision,
                source_hashes=hashes, scenario=scenario, goal=spec["goal"],
                manifest_hash=digest(canonical(manifest)),
                fixture_hash=digest(snapshots[TARGET]) if TARGET in snapshots else None,
                initial={p: digest(b) for p, b in snapshots.items()})
    write_json(run / "meta.json", meta, exclusive=True)
    write_json(run / "state.json", dict(status="prepared"), exclusive=True)
    write_json(run / "evidence.json", {}, exclusive=True)
    return run


class Workspace:
    def __init__(self, run):
        self.run = guard(run)
        self.root = guard(self.run / "workspace", self.run)
        self.meta = read_json(self.run / "meta.json")
        require(tuple(self.meta["source_hashes"]) == tuple(sorted(SOURCES))
                or set(self.meta["source_hashes"]) == set(SOURCES), "invalid_manifest")
        self.evidence = read_json(self.run / "evidence.json")
        self.reads = set()
        self.assert_sources()

    def path(self, value):
        require(name(value) in (*SOURCES, TARGET), "forbidden_path")
        return guard(self.root / value, self.root)

    def state(self):
        return read_json(self.run / "state.json")

    def set_state(self, **value):
        write_json(self.run / "state.json", value)

    def assert_sources(self):
        origin = guard(self.meta["origin"])
        for path, expected in self.meta["source_hashes"].items():
            require(path in SOURCES, "invalid_manifest")
            require(digest(bounded(self.path(path))) == expected, "stale_source")
            require(digest(bounded(guard(origin / path, origin))) == expected, "stale_origin")

    def inventory(self):
        """Do not follow arbitrary directory entries."""
        result = {}
        for path in self.root.rglob("*"):
            guard(path, self.root)
            if path.is_file():
                relative = path.relative_to(self.root).as_posix()
                require(relative in (*SOURCES, TARGET), "unexpected_workspace_file")
                result[relative] = digest(bounded(path))
        return result

    def target_hash(self):
        path = self.path(TARGET)
        return digest(bounded(path)) if path.exists() else None

    def assert_initial(self):
        self.assert_sources()
        require(self.inventory() == self.meta["initial"], "workspace_changed_before_approval")

    def record(self, path, start, end, lines, sha):
        value = dict(path=path, start_line=start, end_line=end, sha256=sha,
                     text="\n".join(lines[start - 1:end]))
        eid = "E" + digest(canonical(value))[:16]
        self.evidence[eid] = value
        return eid

    def save_evidence(self):
        write_json(self.run / "evidence.json", self.evidence)

    def list_files(self):
        self.assert_sources()
        return dict(files=[dict(path=p, exists=self.path(p).exists(),
                                sha256=digest(bounded(self.path(p))) if self.path(p).exists() else None,
                                bytes=self.path(p).stat().st_size if self.path(p).exists() else 0,
                                writable=p == TARGET)
                           for p in (*SOURCES, TARGET)])

    def read_file(self, path, start_line, end_line):
        source = self.path(path)
        if not source.exists():
            return dict(path=path, status="absent")
        require(type(start_line) is int and type(end_line) is int and
                1 <= start_line <= end_line, "invalid_line_range")
        raw = bounded(source)
        lines = raw.decode("utf-8-sig").splitlines()
        require(start_line <= len(lines), "invalid_line_range")
        end_line = min(end_line, len(lines))
        sha = digest(raw)
        result = dict(path=path, sha256=sha, start_line=start_line, end_line=end_line,
                      total_lines=len(lines),
                      lines=[dict(line=i, text=lines[i-1]) for i in range(start_line, end_line+1)])
        require(len(canonical(result).encode("utf-8")) + 80 <= MAX_RESULT,
                "result_size_limit_request_smaller_range")
        result["evidence_id"] = self.record(path, start_line, end_line, lines, sha)
        self.reads.add((path, sha))
        self.save_evidence()
        return result

    def search_text(self, query):
        require(isinstance(query, str) and 0 < len(query) <= 200 and "\n" not in query,
                "invalid_query")
        result = dict(query=query, scope=list(SOURCES), matches=[], complete=True, total_matches=0)
        for path in (*SOURCES, TARGET):
            source = self.path(path)
            if not source.exists():
                continue
            raw = bounded(source)
            lines = raw.decode("utf-8-sig").splitlines()
            sha = digest(raw)
            for i, text in enumerate(lines, 1):
                if query not in text:
                    continue
                result["total_matches"] += 1
                match = dict(path=path, line=i, text=text, sha256=sha)
                if len(canonical(result).encode("utf-8")) + len(canonical(match).encode("utf-8")) + 150 > MAX_RESULT:
                    result["complete"] = False
                    continue
                match["evidence_id"] = self.record(path, i, i, lines, sha)
                result["matches"].append(match)
        result["scope"] = [p for p in (*SOURCES, TARGET) if self.path(p).exists()]
        self.save_evidence()
        return result

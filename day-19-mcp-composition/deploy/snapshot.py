"""Make a source-only snapshot and manifest. No .env, venv or local evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def manifest(root=ROOT):
    files = ["run.py", "requirements.txt", "collect.py", "verify.py", "launch.py"]
    files += [p.relative_to(root).as_posix() for folder in ("composition", "deploy")
              for p in (root / folder).iterdir() if p.is_file() and p.suffix in (".py", ".service", ".fragment", ".example")]
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sorted(files)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    target.mkdir(parents=True, exist_ok=False)
    files = manifest()
    revision = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    (target / "manifest.json").write_text(json.dumps(dict(revision=revision, files=files), indent=2) + "\n", encoding="utf-8")
    with tarfile.open(target / "snapshot.tar.gz", "x:gz") as archive:
        for name in files:
            archive.add(ROOT / name, arcname=name)
        archive.add(target / "manifest.json", arcname="manifest.json")
    print(json.dumps(dict(revision=revision, files=len(files), archive_sha256=hashlib.sha256((target / "snapshot.tar.gz").read_bytes()).hexdigest())))

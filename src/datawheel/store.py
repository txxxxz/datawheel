"""Content-addressed, whole-directory commits for process-interruption recovery."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from .contracts import Record, digest, json_text


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl_text(values) -> str:
    return "".join(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n" for value in values)


def read_records(path: Path, source_hash: str | None = None) -> list[Record]:
    records, seen_ids = [], set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        location = f"{path.name}:{line_number}"
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{location}: invalid JSON: {error.msg}") from error
        record = Record.from_dict(value, location)
        if record.id in seen_ids:
            raise ValueError(f"{location}: duplicate record id {record.id!r}")
        seen_ids.add(record.id)
        if source_hash is not None:
            record = replace(record, provenance={"kind": "imported", "source_sha256": source_hash,
                                                 "line": line_number, "original": record.provenance})
        records.append(record)
    return records


def atomic_write(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def commit_directory(path: Path, files: dict[str, str], previous_hash: str) -> str:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite committed stage: {path}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{path.name}-", dir=path.parent))
    try:
        for name, text in files.items():
            atomic_write(temporary / name, text)
        commit = {"previous_sha256": previous_hash,
                  "files": {name: sha256_file(temporary / name) for name in sorted(files)}}
        atomic_write(temporary / "commit.json", json_text(commit))
        os.replace(temporary, path)
        return digest(commit)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def verify_commit(path: Path, previous_hash: str) -> str:
    commit = read_json(path / "commit.json")
    if commit["previous_sha256"] != previous_hash:
        raise ValueError(f"broken checkpoint chain: {path.name}")
    for name, expected in commit["files"].items():
        if Path(name).name != name or sha256_file(path / name) != expected:
            raise ValueError(f"checkpoint content changed: {path.name}/{name}")
    return digest(commit)

"""Project-local persistence and stable fingerprints."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


class WorkflowError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_bytes(value)
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False, prefix=".write-") as stream:
        stream.write(payload)
        temp_path = Path(stream.name)
    os.replace(temp_path, path)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def value_hash(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def run_dir(project, run):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run) or ".." in run:
        raise WorkflowError("run must be a contained identifier, not a path")
    project = Path(project).resolve()
    target = project / ".ppt-assistant" / "runs" / run
    if not target.resolve().is_relative_to(project):
        raise WorkflowError("run path escapes project")
    return target


def load_state(root):
    state = read_json(root / "state.json")
    if state is None:
        raise WorkflowError("run does not exist; use init first")
    return state


def invalidate(state):
    state["approval"] = None
    state["updated_at"] = utc_now()
    state["stage"] = "planning"

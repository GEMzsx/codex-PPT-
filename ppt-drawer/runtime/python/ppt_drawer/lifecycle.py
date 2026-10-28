"""Review gate and rendering adapter lifecycle."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from .artifacts import approval_error, artifact_bundle, validate_bundle
from .retrospective import auto_retro
from .storage import WorkflowError, utc_now, write_json


def register(run, directory, stage):
    if stage == "full":
        error = approval_error(run)
        if error:
            raise WorkflowError("Current approval is invalid: " + error)
    bundle = artifact_bundle(run,directory,stage)
    state = run.state()
    state[stage] = bundle
    state["stage"] = "awaiting_review" if stage=="sample" else "full_ready"
    if stage == "sample":
        state["approval"] = None
        state["full"] = None
    state.pop("last_error", None)
    run.save(state)
    write_json(run.root / (stage+"-receipt.json"),bundle)
    auto_retro(run,stage,state["stage"],Path(directory)/"render-report.json")
    return run.status()


def approve(run, statement, reviewer):
    if not statement.strip() or not reviewer.strip():
        raise WorkflowError("Approval requires a user statement and reviewer")
    state = run.state()
    bundle = validate_bundle(run,state.get("sample"))
    state["approval"] = {"created_at":utc_now(),"reviewer":reviewer,"statement":statement,"sample_sha256":bundle["sha256"],"plan_sha256":bundle["plan_sha256"],"context_sha256":bundle["context_sha256"]}
    state["stage"] = "approved"
    run.save(state)
    write_json(run.root / "approval.json",state["approval"])
    return run.status()


def finish(run):
    error = approval_error(run)
    if error:
        raise WorkflowError("Current approval is invalid: " + error)
    state = run.state()
    if not state.get("full"):
        raise WorkflowError("No current full presentation artifacts")
    validate_bundle(run,state["full"])
    state["stage"] = "completed"
    state["completed_at"] = utc_now()
    run.save(state)
    auto_retro(run,"full","completed",Path(state["full"]["directory"])/"render-report.json")
    return run.status()


def node_binary(explicit=None):
    if explicit or os.environ.get("PPT_DRAWER_NODE"):
        return explicit or os.environ["PPT_DRAWER_NODE"]
    bundled = Path(sys.executable).parents[1] / "node" / "bin" / ("node.exe" if os.name=="nt" else "node")
    return str(bundled) if bundled.is_file() else shutil.which("node")


def render(run, stage, node=None, renderer=None, output=None, timeout=900):
    from .artifacts import context_fingerprint
    if stage == "full":
        error = approval_error(run)
        if error:
            raise WorkflowError("Current approval is invalid: " + error)
    log_path = run.root / "logs" / (stage+"-"+uuid.uuid4().hex[:10]+".log")
    log_path.parent.mkdir(parents=True,exist_ok=True)
    try:
        context_fingerprint(run)
        renderer = Path(renderer or os.environ.get("PPT_DRAWER_RENDERER") or (Path(__file__).resolve().parents[2] / "js" / "render.mjs"))
        binary = node_binary(node)
        if not binary or not renderer.is_file():
            raise WorkflowError("Rendering adapter unavailable; provide Node and runtime/js/render.mjs")
        directory = Path(output).resolve() if output else run.root / "artifacts" / (stage+"-"+uuid.uuid4().hex[:10])
        if not directory.resolve().is_relative_to(run.project):
            raise WorkflowError("Render output must stay inside the target project")
        if directory.exists() and any(directory.iterdir()):
            raise WorkflowError("Render output must be a new or empty directory")
        directory.mkdir(parents=True,exist_ok=True)
        command = [str(binary),str(renderer.resolve()),"--plan",str(run.root/"plan.json"),"--output",str(directory),"--stage",stage]
        result = subprocess.run(command,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout)
        log_path.write_text(result.stdout+"\n"+result.stderr,encoding="utf-8")
        if result.returncode:
            raise WorkflowError("Rendering failed; inspect " + str(log_path) + ": " + (result.stderr or result.stdout)[-1000:])
        return register(run,directory,stage)
    except (WorkflowError,OSError,subprocess.SubprocessError) as error:
        state = run.state()
        state["last_error"] = str(error)
        run.save(state)
        if not log_path.exists():
            log_path.write_text(str(error),encoding="utf-8")
        auto_retro(run,stage,"failed",log_path)
        raise WorkflowError(str(error)) from error

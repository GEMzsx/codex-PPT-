"""Bind review to the actual plan, source versions and produced sample files."""
from pathlib import Path
import re
import zipfile

from .planning import check_refs, sample_ids, validate_plan, validate_supplement_pages
from .storage import WorkflowError, file_hash, read_json, value_hash


def context_fingerprint(run):
    plan_path = run.root / "plan.json"
    plan = read_json(plan_path)
    if plan is None:
        raise WorkflowError("No page plan; use plan first")
    known = run.known_sources()
    validate_plan(plan,plan_path.parent,known)
    validate_supplement_pages(run.records("supplements"), plan)
    for item in run.records("knowledge"):
        check_refs(item.get("source_ids",[]),known,"knowledge " + item["id"])
    for material in run.records("materials"):
        if material["status"] in {"ready","partial"}:
            path = Path(material["path"])
            if not path.is_file() or file_hash(path) != material["sha256"]:
                raise WorkflowError("Source material changed; re-ingest before review: " + material["path"])
    resources = {}
    if plan.get("template"):
        resources[plan["template"]] = file_hash(plan["template"])
    for slide in plan["slides"]:
        for block in slide["blocks"]:
            if block["type"] == "image":
                resources[block["path"]] = file_hash(block["path"])
    return {
        "plan_sha256":file_hash(plan_path),
        "context_sha256":value_hash({"materials":run.records("materials"),"knowledge":run.records("knowledge"),"supplements":run.records("supplements"),"resources":resources}),
    }


def file_fingerprints(directory):
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            if not path.resolve().is_relative_to(directory.resolve()) or path.is_symlink():
                raise WorkflowError("Artifact symlink escapes its output directory")
            result[path.relative_to(directory).as_posix()] = file_hash(path)
    return result


def artifact_bundle(run, directory, stage):
    directory = Path(directory).resolve()
    if not directory.is_relative_to(run.project):
        raise WorkflowError("Artifacts must stay inside the target project")
    report = read_json(directory / "render-report.json")
    if not isinstance(report,dict):
        raise WorkflowError("Missing render-report.json")
    context = context_fingerprint(run)
    plan = read_json(run.root / "plan.json")
    expected = sample_ids(plan) if stage == "sample" else [s["id"] for s in plan["slides"]]
    if report.get("slide_ids") != expected or report.get("slide_count") != len(expected):
        raise WorkflowError("Rendered slide IDs/count do not match the current plan and stage")
    if report.get("plan_sha256") != context["plan_sha256"]:
        raise WorkflowError("Rendered artifact belongs to a different plan version")
    if report.get("errors"):
        raise WorkflowError("Render report contains errors: " + str(report["errors"]))
    deck = directory / "deck.pptx"
    if not deck.is_file():
        raise WorkflowError("Missing deck.pptx")
    try:
        with zipfile.ZipFile(deck) as archive:
            count = len([n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml",n)])
    except zipfile.BadZipFile as error:
        raise WorkflowError("PPTX is not a readable package") from error
    if count != len(expected):
        raise WorkflowError("PPTX page count differs from render report")
    previews = [p for p in directory.rglob("*") if p.suffix.lower() in {".png",".jpg",".jpeg",".webp"}]
    if len(previews) < len(expected):
        raise WorkflowError("Missing per-slide previews")
    bundle = {"directory":str(directory),"stage":stage,"slide_ids":expected,**context,"files":file_fingerprints(directory)}
    bundle["sha256"] = value_hash(bundle)
    return bundle


def validate_bundle(run, bundle):
    if not bundle:
        raise WorkflowError("No current sample artifact; render a sample first")
    current = artifact_bundle(run, bundle["directory"], bundle["stage"])
    if current["sha256"] != bundle["sha256"]:
        raise WorkflowError("Sample artifacts or source context changed; render/register the sample again")
    return current


def approval_error(run, state=None):
    state = state or run.state()
    approval = state.get("approval")
    if not approval:
        return "No current user approval"
    try:
        bundle = validate_bundle(run,state.get("sample"))
        if approval.get("sample_sha256") != bundle["sha256"] or approval.get("plan_sha256") != bundle["plan_sha256"] or approval.get("context_sha256") != bundle["context_sha256"]:
            return "Approval does not match the current plan, source context and sample"
    except (WorkflowError,OSError,ValueError) as error:
        return str(error)
    return None

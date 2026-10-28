"""Validate page plans and resolve their explicit source references."""
from copy import deepcopy
import math
from pathlib import Path

from .storage import WorkflowError


def references(record):
    refs = record.get("source_ids", [])
    if not isinstance(refs,list):
        raise WorkflowError("source_ids must be a list")
    refs = list(refs)
    if record.get("source_id"):
        refs.append(record["source_id"])
    return refs


def check_refs(refs, known, where):
    if not isinstance(refs, list) or any(not isinstance(x,str) or x not in known for x in refs):
        raise WorkflowError(f"Unknown or invalid source reference in {where}: {refs}")


def validate_supplement_pages(entries, plan):
    ids = {slide["id"] for slide in plan["slides"]} if plan else None
    for item in entries:
        pages = item.get("slide_ids", [])
        if not isinstance(pages,list) or any(not isinstance(page,str) or not page for page in pages):
            raise WorkflowError("Supplement " + item["id"] + " slide_ids must be a list of page IDs")
        if ids is not None and any(page not in ids for page in pages):
            raise WorkflowError("Supplement " + item["id"] + " slide_ids refer to pages absent from the current plan: " + str(pages) + "; update supplement mappings or set slide_ids=[] before changing or rendering the plan")


def sample_ids(plan):
    return plan.get("sample_slide_ids") or [s["id"] for s in plan["slides"][:3]]


def validate_plan(plan, base, known):
    if not isinstance(plan,dict):
        raise WorkflowError("page plan must be an object")
    plan = deepcopy(plan)
    if plan.get("version") != 1 or not isinstance(plan.get("title"), str) or not plan["title"].strip():
        raise WorkflowError("page plan requires version 1 and a title")
    if not isinstance(plan.get("style"), (str, dict)):
        raise WorkflowError("page plan requires a style ID or object")
    slides = plan.get("slides")
    if not isinstance(slides, list) or not slides:
        raise WorkflowError("page plan requires nonempty slides")
    ids = []
    for slide in slides:
        if not isinstance(slide, dict) or not isinstance(slide.get("id"),str) or not slide["id"] or slide["id"] in ids:
            raise WorkflowError("slides need unique nonempty IDs")
        ids.append(slide["id"])
        for field in ("title", "layout", "takeaway"):
            if not isinstance(slide.get(field),str):
                raise WorkflowError(f"slide {slide['id']} requires {field}")
        check_refs(slide.get("source_ids", []), known, slide["id"])
        if not isinstance(slide.get("blocks"), list):
            raise WorkflowError(f"slide {slide['id']} requires blocks")
        for block in slide["blocks"]:
            if not isinstance(block,dict) or block.get("type") not in {"text","image","chart","table","process"}:
                raise WorkflowError(f"Unsupported block in {slide['id']}")
            check_refs(references(block), known, slide["id"])
            if block["type"] == "image":
                path = Path(block.get("path", ""))
                if not path.is_absolute():
                    path = base / path
                if not path.is_file():
                    raise WorkflowError(f"Image is not a readable file: {path}")
                block["path"] = str(path.resolve())
            if block["type"] == "chart":
                categories, series = block.get("categories"), block.get("series")
                if not isinstance(categories,list) or not categories or not isinstance(series,list) or not series:
                    raise WorkflowError("chart requires categories and series")
                for item in series:
                    if not isinstance(item,dict):
                        raise WorkflowError("chart series must be objects")
                    values = item.get("values")
                    if not isinstance(values,list) or len(values)!=len(categories) or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in values):
                        raise WorkflowError("chart values must be finite numbers matching categories")
    selected = sample_ids(plan)
    if not isinstance(selected,list) or len(selected)!=min(3,len(ids)) or len(set(selected))!=len(selected) or any(x not in ids for x in selected):
        raise WorkflowError("sample_slide_ids must select three distinct existing slides (or all slides for a shorter plan)")
    plan["sample_slide_ids"] = selected
    if plan.get("template"):
        path = Path(plan["template"])
        if not path.is_absolute():
            path = base / path
        if not path.is_file():
            raise WorkflowError("template does not exist: " + str(path))
        plan["template"] = str(path.resolve())
    return plan

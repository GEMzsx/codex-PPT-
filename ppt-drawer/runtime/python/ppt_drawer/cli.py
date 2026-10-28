"""Public command-line interface; JSON results are emitted as UTF-8."""
import argparse
import json
from pathlib import Path
import sys

from .storage import WorkflowError, read_json
from .project import ProjectRun


def parser():
    result = argparse.ArgumentParser(description="PPT Drawer project workflow")
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("init", "ingest", "status", "knowledge", "supplement", "plan", "render", "register-sample", "register-full", "approve", "handoff", "retro", "finish"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project", required=True)
        cmd.add_argument("--run", required=True)
        cmd.add_argument("--compact",action="store_true",help="Omit extracted material text from JSON output; complete records remain in the run directory")
        if name == "init":
            cmd.add_argument("--title", default="PPT project")
            cmd.add_argument("--brief")
        if name == "ingest":
            cmd.add_argument("--input", action="append", required=True)
        if name in {"knowledge","supplement","plan"}:
            cmd.add_argument("--input", required=True)
        if name == "render":
            cmd.add_argument("--stage", choices=("sample","full"), required=True)
            cmd.add_argument("--node")
            cmd.add_argument("--renderer")
            cmd.add_argument("--output")
            cmd.add_argument("--timeout",type=int,default=900)
        if name in {"register-sample","register-full"}:
            cmd.add_argument("--directory",required=True)
        if name == "approve":
            cmd.add_argument("--statement",required=True)
            cmd.add_argument("--reviewer",default="user")
        if name == "handoff":
            cmd.add_argument("--role",required=True)
            cmd.add_argument("--agent-id",required=True)
            cmd.add_argument("--input",action="append",default=[])
            cmd.add_argument("--output",action="append",default=[])
            cmd.add_argument("--status",choices=("running","completed","failed"),required=True)
            cmd.add_argument("--summary",default="")
        if name == "retro":
            cmd.add_argument("--stage",required=True)
            cmd.add_argument("--input",required=True)
    return result


def execute(args):
    run = ProjectRun(args.project, args.run)
    if args.command == "init":
        return run.init(args.title, read_json(args.brief) if args.brief else None)
    if args.command == "ingest":
        return run.ingest(args.input)
    if args.command in {"knowledge","supplement","plan"}:
        source = Path(args.input).resolve()
        if not source.is_file():
            raise WorkflowError("JSON input does not exist: " + str(source))
        payload = read_json(source)
        if args.command == "plan":
            return run.plan(payload, source.parent)
        return getattr(run,args.command)(payload)
    if args.command == "render":
        from .lifecycle import render
        return render(run,args.stage,args.node,args.renderer,args.output,args.timeout)
    if args.command in {"register-sample","register-full"}:
        from .lifecycle import register
        return register(run,args.directory,"sample" if args.command=="register-sample" else "full")
    if args.command == "approve":
        from .lifecycle import approve
        return approve(run,args.statement,args.reviewer)
    if args.command == "handoff":
        return run.handoff(args.role,args.agent_id,args.input,args.output,args.status,args.summary)
    if args.command == "retro":
        from .retrospective import record_retro
        source = Path(args.input).resolve()
        if not source.is_file():
            raise WorkflowError("Retrospective input does not exist")
        record_retro(run,args.stage,read_json(source))
        return run.status()
    if args.command == "finish":
        from .lifecycle import finish
        return finish(run)
    return run.status()


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        args = parser().parse_args(argv)
        result = execute(args)
        if args.compact:
            result["materials"] = [{**{k:v for k,v in m.items() if k!="content"},"content_count":len(m["content"])} for m in result.get("materials",[])]
    except (WorkflowError, OSError, ValueError) as error:
        print(json.dumps({"ok":False, "error":str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0

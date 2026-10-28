#!/usr/bin/env python3
"""Run an explicitly synthetic PPT workflow through its public CLI."""
import argparse
import csv
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Demo:
    def __init__(self, args):
        self.args = args
        self.project = args.project.resolve()
        self.plugin = args.plugin.resolve()
        self.cli = self.plugin / "scripts" / "ppt_drawer.py"
        self.run = self.project / ".ppt-assistant" / "runs" / args.run

    def call(self, command, *extra, expect=0, run=None):
        command_line = [sys.executable, "-X", "utf8", str(self.cli), command, "--project", str(self.project), "--run", run or self.args.run, "--compact", *map(str, extra)]
        result = subprocess.run(command_line, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != expect:
            raise ValueError(f"{command} returned {result.returncode}: {result.stdout} {result.stderr}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{command} did not return JSON: {result.stdout} {result.stderr}") from exc

    def prepare(self):
        if self.project.exists() and any(self.project.iterdir()):
            raise ValueError("Demo requires a new or empty project; user files will be preserved")
        materials = self.project / "materials"
        materials.mkdir(parents=True, exist_ok=True)
        for name in ("project.md", "measurements.csv"):
            destination = materials / name
            if destination.exists():
                raise ValueError("Demo refuses to overwrite existing project materials")
            shutil.copyfile(ROOT / "examples" / "demo" / "materials" / name, destination)
        figure = materials / "layout-reference.png"
        shutil.copyfile(ROOT / "examples" / "demo" / "materials" / "example-figure.png", figure)
        self.call("init", "--title", "PPT 助手技术演示：构造数据")
        status = self.call("ingest", "--input", materials)
        sources = {item["name"]: item["id"] for item in status["materials"]}
        replacements = {"$project": sources["project.md"], "$data": sources["measurements.csv"], "$figure": sources[figure.name], "$figure_path": str(figure)}
        def replace(value):
            if isinstance(value, str):
                return replacements.get(value, value)
            if isinstance(value, list):
                return [replace(item) for item in value]
            if isinstance(value, dict):
                return {key: replace(item) for key, item in value.items()}
            return value
        fixture_root = ROOT / "examples" / "demo"
        for fixture, command in (("knowledge-template.json", "knowledge"), ("plan-template.json", "plan")):
            payload = replace(json.loads((fixture_root / fixture).read_text(encoding="utf-8")))
            destination = self.project / "inputs" / fixture.replace("-template", "")
            write_json(destination, payload)
            self.call(command, "--input", destination)
        write_json(self.run / "synthetic-demo.json", {"synthetic": True, "materials": {str(p.resolve()): digest(p) for p in sorted(materials.iterdir())}, "plan_sha256": digest(self.run / "plan.json")})
        return {"ok": True, "phase": "prepare", "project": str(self.project), "run_dir": str(self.run), "synthetic": True}

    def check_demo(self):
        marker = json.loads((self.run / "synthetic-demo.json").read_text(encoding="utf-8"))
        if marker.get("synthetic") is not True or any(digest(Path(name)) != value for name, value in marker["materials"].items()) or digest(self.run / "plan.json") != marker["plan_sha256"]:
            raise ValueError("Synthetic fixture changed; prepare a fresh technical demo")

    def verify_artifacts(self, status, stage):
        directory = Path(status[stage]["directory"])
        report = json.loads((directory / "render-report.json").read_text(encoding="utf-8"))
        expected = ["scope", "workflow", "measurements"] if stage == "sample" else ["cover", "comparison", "scope", "workflow", "measurements", "summary"]
        if report["slide_ids"] != expected:
            raise ValueError("Demo page order differs from its six-page outline")
        native = report["native"]
        if native["charts"] < 1 or native["tables"] < 1 or native["embedded_workbooks"] < 1 or native["images"] < 1:
            raise ValueError("Demo did not retain native chart/table/workbook and source image")
        with zipfile.ZipFile(directory / "deck.pptx") as archive:
            workbooks = [name for name in archive.namelist() if name.startswith("ppt/embeddings/") and name.endswith(".xlsx")]
            from openpyxl import load_workbook
            wb = load_workbook(BytesIO(archive.read(workbooks[0])), data_only=True)
            workbook_rows = [list(sheet.values) for sheet in wb]
            wb.close()
            with (self.project / "materials" / "measurements.csv").open(encoding="utf-8", newline="") as source:
                measurements = list(csv.DictReader(source))
            expected_rows = [("Category", "方案A", "Category", "方案B"), *[(f"第{item['trial']}次", int(item["scheme_a_minutes"]), f"第{item['trial']}次", int(item["scheme_b_minutes"])) for item in measurements]]
            if expected_rows not in workbook_rows:
                raise ValueError("Native chart workbook does not preserve source trial, series and value assignments")
            from PIL import Image
            media_sizes = []
            for name in archive.namelist():
                if name.startswith("ppt/media/"):
                    try:
                        with Image.open(BytesIO(archive.read(name))) as image:
                            media_sizes.append(image.size)
                    except OSError:
                        continue
            with Image.open(self.project / "materials" / "layout-reference.png") as original:
                if original.size not in media_sizes:
                    raise ValueError("Source image bytes/dimensions were not embedded; possible placeholder image")
        if len(list((directory / "previews").glob("*.png"))) != len(expected):
            raise ValueError("Demo is missing per-page previews")
        return {"directory": str(directory), "slide_ids": expected, "native": native}

    def render(self, stage):
        self.check_demo()
        extra = ["--node", self.args.node] if self.args.node else []
        status = self.call("render", "--stage", stage, *extra)
        artifacts = self.verify_artifacts(status, stage)
        if stage == "sample" and status["stage"] != "awaiting_review":
            raise ValueError("Sample did not remain awaiting review")
        return status, artifacts

    def full(self):
        if not self.args.simulate_review:
            raise ValueError("Full technical demo requires explicit --simulate-review; real user approval must come from the user")
        self.check_demo()
        self.call("approve", "--reviewer", "synthetic-test-harness", "--statement", "仅限明确构造的软件技术演示：模拟确认当前大纲及三页样稿；此记录不代表用户对真实科研内容的确认。")
        status, artifacts = self.render("full")
        status = self.call("finish")
        if status["stage"] != "completed" or not any(item["stage"] == "full" for item in status["retrospectives"]):
            raise ValueError("Demo delivery is missing completion or retrospective")
        return {"ok": True, "phase": "full", "synthetic": True, "artifacts": artifacts, "stage": status["stage"]}

    def gates(self):
        if not self.args.simulate_review:
            raise ValueError("Gate probes require explicit --simulate-review for synthetic fixtures")
        self.check_demo()
        current = self.call("status")
        if not current.get("sample"):
            raise ValueError("Render the three-page sample before gate probes")
        probe = self.args.run + "-gate-probe"
        self.call("init", "--title", "独立确认失效技术探针", run=probe)
        self.call("ingest", "--input", self.project / "materials", run=probe)
        self.call("knowledge", "--input", self.project / "inputs" / "knowledge.json", run=probe)
        self.call("plan", "--input", self.project / "inputs" / "plan.json", run=probe)
        self.call("register-sample", "--directory", current["sample"]["directory"], run=probe)
        approved = self.call("approve", "--reviewer", "synthetic-test-harness", "--statement", "仅供确认失效负向测试，模拟当前构造数据样稿确认。", run=probe)
        if not approved["approval_valid"]:
            raise ValueError("Gate probe approval did not bind to the current sample")
        findings = {"current_sample_approval_valid": True}
        source = self.project / "materials" / "measurements.csv"
        original = source.read_bytes()
        blocked_output = self.project / "must-not-be-created"
        try:
            source.write_bytes(original + b"\n# synthetic mutation probe\n")
            changed = self.call("status", run=probe)
            denied = self.call("render", "--stage", "full", "--output", blocked_output, expect=2, run=probe)
            if changed["approval_valid"] or "changed" not in denied.get("error", "").lower() or blocked_output.exists():
                raise ValueError("Changed source did not invalidate approval before rendering")
            findings["changed_source_full_blocked"] = denied["error"]
        finally:
            source.write_bytes(original)
        plan = json.loads((self.project / "inputs" / "plan.json").read_text(encoding="utf-8"))
        plan["slides"][0]["title"] = "修改后的技术探针封面"
        revised = self.project / "inputs" / "probe-revised-plan.json"
        write_json(revised, plan)
        changed = self.call("plan", "--input", revised, run=probe)
        denied = self.call("render", "--stage", "full", "--output", blocked_output, expect=2, run=probe)
        if changed["approval_valid"] or changed["approval"] is not None or blocked_output.exists():
            raise ValueError("Changed plan did not clear approval before rendering")
        findings["changed_plan_full_blocked"] = denied["error"]
        evidence = self.project / "gate-checks.json"
        write_json(evidence, {"synthetic": True, "probe_run": probe, **findings})
        return {"ok": True, "phase": "gates", "evidence": str(evidence), **findings}

    def verify(self):
        self.check_demo()
        status = self.call("status")
        if status["stage"] != "completed" or not status["approval_valid"]:
            raise ValueError("Demo does not have a completed full deck with current approval")
        return {"ok": True, "phase": "verify", "synthetic": True, "sample": self.verify_artifacts(status, "sample"), "full": self.verify_artifacts(status, "full")}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--plugin", type=Path, default=ROOT / "ppt-drawer")
    parser.add_argument("--run", default="technical-demo")
    parser.add_argument("--phase", choices=("prepare", "sample", "gates", "full", "verify"), required=True)
    parser.add_argument("--node")
    parser.add_argument("--simulate-review", action="store_true", help="Explicitly simulate review only for the unchanged synthetic demo fixtures")
    args = parser.parse_args()
    try:
        demo = Demo(args)
        if args.phase == "prepare":
            result = demo.prepare()
        elif args.phase == "sample":
            denied = demo.call("render", "--stage", "full", expect=2)
            if "approval" not in denied.get("error", "").lower():
                raise ValueError("Unapproved full deck was not blocked by review")
            _, artifacts = demo.render("sample")
            result = {"ok": True, "phase": "sample", "synthetic": True, "unapproved_full_blocked": True, "artifacts": artifacts}
        elif args.phase == "gates":
            result = demo.gates()
        elif args.phase == "verify":
            result = demo.verify()
        else:
            result = demo.full()
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

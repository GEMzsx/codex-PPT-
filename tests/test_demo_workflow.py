"""Exercise the public technical-demo command without requiring Office."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "demo_workflow.py"


class DemoWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / "tmp" / "demo-tests" / uuid.uuid4().hex
        self.project = self.base / "中文项目"

    def tearDown(self):
        if self.base.exists():
            self.assertTrue(self.base.resolve().is_relative_to((ROOT / "tmp" / "demo-tests").resolve()))
            shutil.rmtree(self.base)

    def call(self, phase, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--project", str(self.project), "--phase", phase, *args], capture_output=True, text=True, encoding="utf-8")

    def test_prepare_creates_source_bound_six_page_demo_and_waits_for_review(self):
        result = self.call("prepare")
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["ok"])
        run = self.project / ".ppt-assistant" / "runs" / "technical-demo"
        state = json.loads((run / "state.json").read_text(encoding="utf-8"))
        plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
        materials = json.loads((run / "materials.json").read_text(encoding="utf-8"))
        self.assertIsNone(state["approval"])
        self.assertIsNone(state["full"])
        self.assertEqual(len(plan["slides"]), 6)
        self.assertEqual(plan["sample_slide_ids"], ["scope", "workflow", "measurements"])
        chart = next(slide for slide in plan["slides"] if slide["id"] == "measurements")["blocks"][0]
        self.assertEqual(chart["series"][0]["values"], [18, 20, 16])
        self.assertEqual(chart["series"][1]["values"], [12, 14, 10])
        sources = {m["id"] for m in materials}
        self.assertTrue(all(set(s["source_ids"]) <= sources for s in plan["slides"]))
        self.assertIn("构造", (self.project / "materials" / "project.md").read_text(encoding="utf-8"))
        self.assertIn("没有登记联网补充", (run / "supplemental-knowledge.md").read_text(encoding="utf-8"))

    def test_full_demo_requires_explicit_synthetic_review_flag(self):
        self.assertEqual(self.call("prepare").returncode, 0)
        result = self.call("full")
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stdout)["error"]
        self.assertIn("--simulate-review", error)
        state = json.loads((self.project / ".ppt-assistant" / "runs" / "technical-demo" / "state.json").read_text(encoding="utf-8"))
        self.assertIsNone(state["approval"])

    def test_demo_refuses_an_existing_project_with_user_files(self):
        self.project.mkdir(parents=True)
        original = self.project / "research.md"
        original.write_text("User research, preserve this file", encoding="utf-8")
        result = self.call("prepare")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(original.read_text(encoding="utf-8"), "User research, preserve this file")
        self.assertFalse((self.project / ".ppt-assistant").exists())


if __name__ == "__main__":
    unittest.main()

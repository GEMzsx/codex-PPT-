"""Public CLI contracts for a self-contained distributable Codex plugin."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import shutil
import sys
import unittest
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class PluginPackageTests(unittest.TestCase):
    def setUp(self):
        temp_root = ROOT / "tmp" / "plugin-tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.workspace = temp_root / ("case-" + uuid.uuid4().hex)
        self.workspace.mkdir()
        self.addCleanup(self.cleanup_workspace)
        self.plugin = self.workspace / "ppt-drawer"
        self.plugin.mkdir()
        interface = {
            "displayName": "PPT 助手",
            "shortDescription": "按项目材料制作可编辑PPT",
            "category": "Productivity",
            "capabilities": [],
            "defaultPrompt": "根据项目材料制作汇报，先提供大纲和三页样稿。",
        }
        self.write_json("plugin.json", {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": "ppt-drawer",
            "version": "0.1.0",
            "description": "Create editable project presentations.",
            "extensions": {"com.openai": {"requires_local_executor": True, "interface": interface}},
        })
        self.write_json(".codex-plugin/plugin.json", {
            "name": "ppt-drawer",
            "version": "0.1.0",
            "description": "Create editable project presentations.",
            "requires_local_executor": True,
            "skills": "./skills",
            "interface": interface,
        })
        self.write("skills/ppt-assistant/SKILL.md", "---\nname: ppt-assistant\ndescription: Create editable project presentations from supplied material.\n---\n\nCreate the requested presentation.\n")

    def write(self, path: str, content: str):
        target = self.plugin / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def cleanup_workspace(self):
        allowed = (ROOT / "tmp" / "plugin-tests").resolve()
        target = self.workspace.resolve()
        if target.parent != allowed:
            raise RuntimeError("test cleanup target escaped the test workspace")
        shutil.rmtree(target)

    def write_json(self, path: str, content: dict):
        self.write(path, json.dumps(content, ensure_ascii=False, indent=2))

    def cli(self, tool: str, *args: str):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "tools" / tool), *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def add_runtime(self):
        self.write("scripts/ppt_drawer.py", '"""Fixture command, not the product runtime."""\nprint("fixture runtime")\n')
        self.write("runtime/python/ppt_drawer/__init__.py", '"""Fixture package."""\n')
        self.write("runtime/js/render.mjs", 'export const fixtureVersion = 1;\n')

    def test_valid_self_contained_plugin_is_accepted(self):
        result = self.cli("validate_plugin.py", "--plugin", self.plugin, "--json")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["skills"], ["ppt-assistant"])

    def test_missing_role_reference_is_reported_before_distribution(self):
        skill = self.plugin / "skills/ppt-assistant/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nRead [writer](references/writer.md).\n", encoding="utf-8")
        result = self.cli("validate_plugin.py", "--plugin", self.plugin, "--json")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("references/writer.md", " ".join(json.loads(result.stdout)["errors"]))

    def test_complex_agent_yaml_is_reported_as_unsupported(self):
        self.write("skills/ppt-assistant/agents/openai.yaml", "interface:\n  display_name: |\n    Multiple lines\n  short_description: A useful presentation skill\n")
        result = self.cli("validate_plugin.py", "--plugin", self.plugin, "--json")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("unsupported YAML", " ".join(json.loads(result.stdout)["errors"]))

    def test_package_contains_one_plugin_and_a_separate_local_marketplace(self):
        self.add_runtime()
        self.write("node_modules/private.json", '{"private":"dependency"}')
        self.write(".git/config", "private repository state")
        self.write("assets/private-paper.pdf", "private research material")
        result = self.cli("package_plugin.py", "--plugin", self.plugin, "--output", self.workspace / "dist", "--marketplace-name", "ppt-drawer-local")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        with zipfile.ZipFile(report["archive"]) as archive:
            names = set(archive.namelist())
        self.assertIn("ppt-drawer/plugin.json", names)
        self.assertIn("ppt-drawer/scripts/ppt_drawer.py", names)
        self.assertIn("ppt-drawer/skills/ppt-assistant/SKILL.md", names)
        self.assertTrue(all(name.startswith("ppt-drawer/") for name in names))
        self.assertFalse(any(part in name for name in names for part in ("node_modules", ".git/", "private-paper", "marketplace.json")))
        marketplace = Path(report["marketplace"])
        listing = json.loads(marketplace.read_text(encoding="utf-8"))
        self.assertEqual(listing["plugins"][0]["source"], {"source": "local", "path": "./plugins/ppt-drawer"})
        installed_source = marketplace.parents[2] / "plugins" / "ppt-drawer"
        validation = self.cli("validate_plugin.py", "--plugin", installed_source, "--require-runtime", "--json")
        self.assertEqual(validation.returncode, 0, validation.stderr + validation.stdout)

    def test_project_path_cannot_leak_through_a_packaged_knowledge_asset(self):
        self.add_runtime()
        self.write_json("assets/style-catalog.json", {"source_path": "Q:/Mock/private-paper.pdf"})
        result = self.cli("package_plugin.py", "--plugin", self.plugin, "--output", self.workspace / "dist")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("host-specific", json.loads(result.stdout)["error"])
        self.assertFalse(list((self.workspace / "dist").glob("*.zip")))

    def test_repository_entrypoint_and_reusable_style_catalog_are_discoverable(self):
        plugin = ROOT / "ppt-drawer"
        result = self.cli("validate_plugin.py", "--plugin", plugin, "--json")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["skills"], ["ppt-assistant"])
        catalog = json.loads((plugin / "assets" / "style-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(len(catalog["profiles"]), 6)
        self.assertEqual(len(catalog["layouts"]), 26)
        self.assertEqual(next(p for p in catalog["profiles"] if p["id"] == "blue_layered")["ratio"], "16:10")
        self.assertNotIn("slides", catalog)
        self.assertNotIn("sources", catalog)

    def test_skill_invocation_policy_uses_a_boolean_not_a_quoted_string(self):
        self.write("skills/ppt-assistant/SKILL.md", '---\nname: ppt-assistant\ndescription: "Create slides: preserve the project evidence."\ndisable-model-invocation: "false"\n---\nCreate the requested presentation.\n')
        result = self.cli("validate_plugin.py", "--plugin", self.plugin, "--json")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("disable-model-invocation must be a boolean", " ".join(json.loads(result.stdout)["errors"]))

    def test_invalid_manifest_shape_produces_json_diagnostics(self):
        manifest = json.loads((self.plugin / "plugin.json").read_text(encoding="utf-8"))
        manifest["extensions"] = []
        self.write_json("plugin.json", manifest)
        result = self.cli("validate_plugin.py", "--plugin", self.plugin, "--json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("extensions", " ".join(json.loads(result.stdout)["errors"]))


if __name__ == "__main__":
    unittest.main()

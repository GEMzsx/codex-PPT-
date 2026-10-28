#!/usr/bin/env python3
"""Validate the observable metadata of a local Codex plugin."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

PORTABLE_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
COMPONENT_DIRS = {".codex-plugin", "skills", "assets", "scripts", "runtime"}
ROOT_FILES = {"plugin.json", "requirements.txt", "LICENSE", "NOTICE"}
EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "tmp", "dist", "previews", "evidence", "raw"}
SOURCE_SUFFIXES = {".pdf", ".ppt", ".pptx", ".docx", ".xlsx", ".csv", ".sqlite", ".db", ".zip", ".pyc"}


def distribution_files(plugin: Path) -> tuple[list[Path], list[str]]:
    """Select plugin components, leaving build dependencies and research inputs out."""
    plugin = plugin.resolve()
    selected: list[Path] = []
    excluded: list[str] = []
    for directory, directories, files in os.walk(plugin, followlinks=False):
        current = Path(directory)
        relative = current.relative_to(plugin)
        retained = []
        for name in sorted(directories):
            item = current / name
            if name in EXCLUDED_DIRS or (not relative.parts and name not in COMPONENT_DIRS):
                excluded.append(item.relative_to(plugin).as_posix() + "/")
            elif item.is_symlink():
                raise ValueError(f"distribution directory must not be a symlink: {item.relative_to(plugin)}")
            else:
                retained.append(name)
        directories[:] = retained
        for name in sorted(files):
            item = current / name
            key = item.relative_to(plugin).as_posix()
            if (not relative.parts and name not in ROOT_FILES) or item.suffix.lower() in SOURCE_SUFFIXES or name == ".env" or name.startswith(".env.") or name in {"auth.json", "credentials.json", "secrets.json"}:
                excluded.append(key)
                continue
            if item.is_symlink():
                raise ValueError(f"distribution file must not be a symlink: {key}")
            if item.stat().st_size > 5 * 1024 * 1024:
                raise ValueError(f"distribution file exceeds 5 MiB: {key}")
            selected.append(item)
    return sorted(selected), sorted(excluded)


def parse_metadata(text: str) -> dict:
    """Read this package's scalar-mapping YAML subset; diagnose unsupported YAML."""
    values = {}
    stack = [{"indent": -1, "children": 0, "value": values}]
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line[:len(line) - len(line.lstrip())]:
            raise ValueError("unsupported YAML indentation: use spaces")
        indent = len(line) - len(line.lstrip(" "))
        match = re.fullmatch(r"([A-Za-z_][\w-]*):(?:\s*(.*))?", line.lstrip(" "))
        if not match:
            raise ValueError("unsupported YAML: use scalar mappings without block strings, sequences or aliases")
        key, value = match.groups()
        value = (value or "").strip()
        while len(stack) > 1 and indent <= stack[-1]["indent"]:
            stack.pop()
        frame = stack[-1]
        if frame["children"] is None:
            frame["children"] = indent
        if indent != frame["children"]:
            raise ValueError("unsupported YAML indentation")
        mapping = frame["value"]
        if key in mapping:
            raise ValueError(f"duplicate metadata key: {key}")
        if not value:
            child = {}
            mapping[key] = child
            stack.append({"indent": indent, "children": None, "value": child})
            continue
        if value.startswith('"'):
            try:
                scalar, end = json.JSONDecoder().raw_decode(value)
                if value[end:].strip() and not value[end:].lstrip().startswith("#"):
                    raise ValueError("trailing text after quoted scalar")
                value = scalar
            except ValueError as exc:
                raise ValueError(f"unsupported YAML quoted scalar: {exc}") from exc
        elif value.startswith("'"):
            quote = re.match(r"'(?:[^']|'')*'", value)
            if not quote or (value[quote.end():].strip() and not value[quote.end():].lstrip().startswith("#")):
                raise ValueError("unterminated quoted metadata value")
            value = quote.group()[1:-1].replace("''", "'")
        else:
            value = value.split(" #", 1)[0].strip()
            if value[0] in "[{|>&*!" or ": " in value:
                raise ValueError("unsupported YAML: complex scalars require a full YAML parser")
            if value in ("true", "false", "null"):
                value = json.loads(value)
            elif re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?", value):
                value = json.loads(value)
        mapping[key] = value
    return values


def validate_plugin(plugin: Path, require_runtime: bool = False) -> dict:
    plugin = plugin.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    report = {"ok": False, "plugin_name": None, "skills": [], "errors": errors, "warnings": warnings}

    def read_json(relative: str):
        try:
            value = json.loads((plugin / relative).read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError("expected a JSON object")
            return value
        except (OSError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
            return {}

    portable = read_json("plugin.json")
    compat = read_json(".codex-plugin/plugin.json")
    name = portable.get("name")
    report["plugin_name"] = name
    if not isinstance(name, str) or not NAME.fullmatch(name) or len(name) > 64:
        errors.append("plugin.json: name must be a kebab-case identifier of at most 64 characters")
    elif plugin.name != name:
        errors.append("plugin.json: name must match the plugin directory name")
    if portable.get("$schema") != PORTABLE_SCHEMA:
        errors.append("plugin.json: missing portable Agent Plugins 1.0 schema")
    if not isinstance(portable.get("version"), str) or not SEMVER.fullmatch(portable["version"]):
        errors.append("plugin.json: version must use semantic versioning")
    for field in ("name", "version", "description"):
        if portable.get(field) != compat.get(field):
            errors.append(f"manifest mismatch: {field}")
    for field in ("skills", "mcpServers", "apps", "interface"):
        if field in portable:
            errors.append(f"plugin.json: {field} belongs outside the portable top level")
    extensions = portable.get("extensions", {})
    if not isinstance(extensions, dict):
        errors.append("plugin.json: extensions must be an object")
        extensions = {}
    openai = extensions.get("com.openai", {})
    if not isinstance(openai, dict):
        errors.append("plugin.json: extensions.com.openai must be an object")
        openai = {}
    interface = openai.get("interface", {})
    if not isinstance(interface, dict) or not interface.get("displayName"):
        errors.append("plugin.json: a nonblank interface.displayName is required for this local package")
        interface = {}
    if interface != compat.get("interface", {}):
        errors.append("manifest mismatch: interface")
    if openai.get("requires_local_executor") != compat.get("requires_local_executor"):
        errors.append("manifest mismatch: requires_local_executor")
    subtitle = interface.get("shortDescription", "")
    if not isinstance(subtitle, str) or not subtitle.strip() or len(subtitle) > 30:
        errors.append("interface.shortDescription must contain 1–30 characters")
    if not isinstance(interface.get("capabilities", []), list):
        errors.append("interface.capabilities must be an array")
    if compat.get("skills") not in ("./skills", "./skills/"):
        errors.append("compatibility manifest must point skills to ./skills")
    for skill in sorted((plugin / "skills").glob("*/SKILL.md")):
        try:
            text = skill.read_text(encoding="utf-8")
            match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
            if not match:
                raise ValueError("missing YAML frontmatter")
            metadata = parse_metadata(match.group(1))
            if metadata.get("name") != skill.parent.name or not NAME.fullmatch(skill.parent.name):
                raise ValueError("skill name must match its kebab-case directory")
            if not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
                raise ValueError("description must be a nonblank string")
            if "disable-model-invocation" in metadata and not isinstance(metadata["disable-model-invocation"], bool):
                raise ValueError("disable-model-invocation must be a boolean")
            report["skills"].append(metadata["name"])
            agent_yaml = skill.parent / "agents" / "openai.yaml"
            if agent_yaml.is_file():
                agent = parse_metadata(agent_yaml.read_text(encoding="utf-8"))
                ui = agent.get("interface", {})
                if not isinstance(ui, dict) or any(not isinstance(ui.get(key), str) or not ui[key].strip() for key in ("display_name", "short_description")):
                    raise ValueError("agents/openai.yaml: interface needs display_name and short_description strings")
                if "default_prompt" in ui and (not isinstance(ui["default_prompt"], str) or not ui["default_prompt"].strip()):
                    raise ValueError("agents/openai.yaml: default_prompt must be one nonblank string")
                policy = agent.get("policy", {})
                if isinstance(policy, dict) and "allow_implicit_invocation" in policy and not isinstance(policy["allow_implicit_invocation"], bool):
                    raise ValueError("agents/openai.yaml: allow_implicit_invocation must be a boolean")
        except (OSError, ValueError) as exc:
            errors.append(f"{skill.relative_to(plugin).as_posix()}: {exc}")
    if not report["skills"]:
        errors.append("package must contain at least one usable skill")
    try:
        selected, excluded = distribution_files(plugin)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        selected, excluded = [], []
    report["files"] = [path.relative_to(plugin).as_posix() for path in selected]
    report["excluded"] = excluded
    for path in selected:
        if path.suffix.lower() in {".json", ".yaml", ".yml", ".md", ".py", ".js", ".mjs", ".cjs"}:
            try:
                content = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as exc:
                errors.append(f"{path.relative_to(plugin).as_posix()}: cannot read packaged text: {exc}")
                continue
            if re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]", content):
                errors.append(f"{path.relative_to(plugin).as_posix()}: host-specific absolute path in distributable content")
    if require_runtime:
        for relative in ("scripts/ppt_drawer.py", "runtime/python/ppt_drawer/__init__.py", "runtime/js/render.mjs"):
            if relative not in report["files"]:
                errors.append(f"missing runtime entrypoint: {relative}")
    for document in (path for path in selected if path.suffix.lower() == ".md"):
        text = document.read_text(encoding="utf-8")
        text = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1\s*$", "", text)
        for raw in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = raw.strip().strip("<>")
            parts = urlsplit(target)
            if parts.scheme in ("https", "http", "mailto") or target.startswith("#"):
                continue
            relative = unquote(parts.path)
            if parts.scheme or Path(relative).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", relative):
                errors.append(f"{document.relative_to(plugin).as_posix()}: reference must be contained in plugin: {raw}")
                continue
            destination = (document.parent / relative).resolve()
            if not destination.is_relative_to(plugin):
                errors.append(f"{document.relative_to(plugin).as_posix()}: reference escapes plugin: {raw}")
            elif not destination.is_file():
                errors.append(f"{document.relative_to(plugin).as_posix()}: missing reference: {raw}")
    report["ok"] = not errors
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--require-runtime", action="store_true", help="Require the PPT workflow and renderer entrypoints")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable diagnostics")
    args = parser.parse_args()
    report = validate_plugin(args.plugin, args.require_runtime)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print("Plugin valid" if report["ok"] else "Plugin invalid")
        for error in report["errors"]:
            print(f"ERROR: {error}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

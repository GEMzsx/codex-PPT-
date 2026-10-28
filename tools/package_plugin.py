#!/usr/bin/env python3
"""Build a standalone plugin ZIP and an independent local marketplace tree."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
import zipfile

from validate_plugin import NAME, validate_plugin


MARKER = ".ppt-drawer-generated"


def build(plugin: Path, output: Path, marketplace_name: str) -> dict:
    plugin, output = plugin.resolve(), output.resolve()
    if not NAME.fullmatch(marketplace_name) or len(marketplace_name) > 64:
        raise ValueError("marketplace name must be a kebab-case identifier of at most 64 characters")
    if output == plugin or output.is_relative_to(plugin):
        raise ValueError("output must be outside the plugin source directory")
    validation = validate_plugin(plugin, require_runtime=True)
    if not validation["ok"]:
        raise ValueError("source validation failed: " + "; ".join(validation["errors"]))
    manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8-sig"))
    name, version = manifest["name"], manifest["version"]
    market = output / "local-marketplace"
    if market.exists() and (market.is_symlink() or not (market / MARKER).is_file()):
        raise ValueError("refuse to replace a local-marketplace directory not created by this packager")
    output.mkdir(parents=True, exist_ok=True)
    stage = output / (".ppt-drawer-build-" + uuid.uuid4().hex)
    stage.mkdir()
    try:
        staged_market = stage / "local-marketplace"
        staged_plugin = staged_market / "plugins" / name
        for relative in validation["files"]:
            destination = staged_plugin / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(plugin / relative, destination)
        staged_validation = validate_plugin(staged_plugin, require_runtime=True)
        if not staged_validation["ok"]:
            raise ValueError("staged plugin is not self-contained: " + "; ".join(staged_validation["errors"]))
        listing = {
            "name": marketplace_name,
            "interface": {"displayName": "PPT 助手（本地）"},
            "plugins": [{
                "name": name,
                "source": {"source": "local", "path": f"./plugins/{name}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": manifest["extensions"]["com.openai"]["interface"]["category"],
            }],
        }
        marketplace = staged_market / ".agents" / "plugins" / "marketplace.json"
        marketplace.parent.mkdir(parents=True, exist_ok=True)
        marketplace.write_text(json.dumps(listing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staged_market / MARKER).write_text(json.dumps({"plugin": name, "version": version}), encoding="utf-8")
        staged_zip = stage / f"{name}-{version}.zip"
        with zipfile.ZipFile(staged_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative in staged_validation["files"]:
                archive.write(staged_plugin / relative, f"{name}/{relative}")
        with zipfile.ZipFile(staged_zip) as archive:
            if archive.testzip() is not None:
                raise ValueError("archive CRC verification failed")
        archive_path = output / staged_zip.name
        if market.exists():
            resolved = market.resolve()
            if resolved.parent != output or not (resolved / MARKER).is_file():
                raise ValueError("generated marketplace cleanup escaped output")
            shutil.rmtree(resolved)
        shutil.copytree(staged_market, market)
        os.replace(staged_zip, archive_path)
        return {
            "ok": True,
            "archive": str(archive_path),
            "marketplace": str(market / ".agents" / "plugins" / "marketplace.json"),
            "plugin_dir": str(market / "plugins" / name),
            "file_count": len(staged_validation["files"]),
            "excluded": validation["excluded"],
        }
    finally:
        resolved_stage = stage.resolve()
        if resolved_stage.parent != output or not resolved_stage.name.startswith(".ppt-drawer-build-"):
            raise RuntimeError("staging cleanup escaped output")
        if resolved_stage.exists():
            shutil.rmtree(resolved_stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, default=Path(__file__).resolve().parents[1] / "ppt-drawer")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "dist")
    parser.add_argument("--marketplace-name", default="ppt-drawer-local")
    args = parser.parse_args()
    try:
        report = build(args.plugin, args.output, args.marketplace_name)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

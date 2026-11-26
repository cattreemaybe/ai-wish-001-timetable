"""Build a DSH plugin staging directory and npm tarball.

Usage:
  python dsh-plugin/packaging/stage.py --platform darwin --python-source /path/to/runtime --out dist/dsh-aiwish-timetable-darwin
  python dsh-plugin/packaging/stage.py --platform win32 --python-source /path/to/runtime --out dist/dsh-aiwish-timetable-win32

`--python-source` must point at a relocatable Python runtime: on macOS the
directory containing bin/python3; on Windows the directory containing python.exe.
Run the commands in packaging/README.md first to prepare a relocatable runtime.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = ROOT / "dsh-plugin" / "src"
FRONTEND_DIST = ROOT / "frontend" / "dist"

PLATFORM_INFO = {
    "darwin": {"tag": "darwin-arm64", "node_platform": "darwin", "pkg_suffix": "darwin"},
    "win32": {"tag": "win32-x64", "node_platform": "win32", "pkg_suffix": "win32"},
}


def copytree(src: Path, dst: Path, ignore=None):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["darwin", "win32"], required=True)
    ap.add_argument("--python-source", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--no-pack", action="store_true")
    args = ap.parse_args()
    info = PLATFORM_INFO[args.platform]
    out = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # Host and client entries
    copytree(PLUGIN_SRC / "lib", out / "lib")
    shutil.copy2(PLUGIN_SRC / "cordis.patch.yml", out / "cordis.patch.yml")
    shutil.copy2(PLUGIN_SRC / "README.md" if (PLUGIN_SRC / "README.md").exists() else PLUGIN_SRC / "cordis.patch.yml", out / "README.md")
    icon = PLUGIN_SRC / "icon.svg"
    if icon.exists():
        shutil.copy2(icon, out / "icon.svg")
    for extra in ("THIRD_PARTY_NOTICES.md", "LICENSE"):
        src = ROOT / "dsh-plugin" / extra
        if src.exists():
            shutil.copy2(src, out / extra)

    # Web app
    if not (FRONTEND_DIST / "index.html").exists():
        raise SystemExit("frontend/dist 不存在，请先 cd frontend && pnpm run build")
    copytree(FRONTEND_DIST, out / "app")

    # Python engine + API sidecar
    server = out / "server"
    (server / "engine").mkdir(parents=True)
    copytree(ROOT / "engine" / "aiwish", server / "engine" / "aiwish")
    (server / "backend" / "app").mkdir(parents=True)
    for name in ("__init__.py", "main.py", "db.py", "excel_io.py", "serializers.py", "plugin_server.py"):
        shutil.copy2(ROOT / "backend" / "app" / name, server / "backend" / "app" / name)
    # Python caches never ship.
    for pycache in list(server.rglob("__pycache__")):
        shutil.rmtree(pycache, ignore_errors=True)

    # Runtime
    runtime = out / "runtime"
    copytree(args.python_source, runtime)

    package = {
        "name": "dsh-aiwish-timetable",
        "version": "0.2.1",
        "description": "AI-WISH 新高考智能走班排课工作台（DSH 插件，本地 CP-SAT）",
        "type": "module",
        "main": "lib/index.js",
        "exports": {
            ".": "./lib/index.js",
            "./client": "./lib/client.js",
            "./package.json": "./package.json",
        },
        "files": ["lib", "app", "server", "runtime", "cordis.patch.yml", "README.md", "icon.svg", "THIRD_PARTY_NOTICES.md", "LICENSE"],
        "dsh": {
            "manifestVersion": 1,
            "bundle": {
                "patch": "./cordis.patch.yml",
                "platforms": [info["node_platform"]],
            },
            "client": {"inject": [], "platform": "web"},
        },
        "engines": {"node": ">=20"},
        "keywords": ["dsh-plugin", "timetable", "school", "cp-sat", "ai-wish"],
        "license": "MIT",
        "private": True,
    }
    (out / "package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"staged: {out}")
    print(f"size: {sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) / 1024 / 1024:.1f} MB")
    if not args.no_pack:
        import subprocess
        result = subprocess.run(
            ["npm", "pack", "--cache", str(ROOT / ".npm-cache")],
            cwd=out, text=True, capture_output=True,
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
        print(result.stdout.strip().splitlines()[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Static checks for the two platform plugin packages and ZIP wrappers."""
from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_package(folder: str, platform: str, python_rel: str) -> None:
    out = DIST / folder
    tgz = next(out.glob("*.tgz"))
    with tarfile.open(tgz, "r:gz") as tf:
        names = set(tf.getnames())
        def has(suffix: str) -> bool:
            return any(n.endswith(suffix) for n in names)
        assert "package/package.json" in names, folder
        assert has("lib/index.js"), folder
        assert has("lib/client.js"), folder
        assert has("app/index.html"), folder
        assert has("server/backend/app/plugin_server.py"), folder
        assert has("server/engine/aiwish/solver.py"), folder
        assert has("THIRD_PARTY_NOTICES.md"), folder
        assert has(python_rel), f"{folder}: missing {python_rel}"
        manifest = json.loads(tf.extractfile("package/package.json").read())  # type: ignore[arg-type]
        assert manifest["name"] == "dsh-aiwish-timetable"
        assert manifest["dsh"]["bundle"]["platforms"] == [platform]
        assert manifest["dsh"]["client"]["platform"] == "web"
        client = tf.extractfile("package/lib/client.js").read().decode("utf-8")  # type: ignore[arg-type]
        assert "id: 'dsh-aiwish-timetable'" in client
    print(f"OK {folder}: {tgz.name} {tgz.stat().st_size/1024/1024:.1f} MB {sha256(tgz)[:16]}…")


def check_zip(zip_path: Path, expected_tgz_hash: str) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "dsh-aiwish-timetable-0.2.1.tgz" in names
        data = zf.read("SHA256SUMS.txt").decode("utf-8")
        assert expected_tgz_hash in data
        assert "INSTALL.md" in names
    print(f"OK {zip_path.name}")


def main() -> int:
    check_package("dsh-aiwish-timetable-darwin", "darwin", "runtime/bin/python3")
    check_package("dsh-aiwish-timetable-win32", "win32", "runtime/python.exe")
    check_zip(DIST / "AI-WISH-001-DSH-darwin-arm64.zip",
              sha256(DIST / "dsh-aiwish-timetable-darwin/dsh-aiwish-timetable-0.2.1.tgz"))
    check_zip(DIST / "AI-WISH-001-DSH-win32-x64.zip",
              sha256(DIST / "dsh-aiwish-timetable-win32/dsh-aiwish-timetable-0.2.1.tgz"))
    # Windows binary structure
    win = DIST / "dsh-aiwish-timetable-win32/runtime"
    assert (win / "python.exe").read_bytes()[:2] == b"MZ"
    assert (win / "python312.dll").exists()
    assert (win / "python312._pth").exists()
    assert (win / "Lib/site-packages/ortools/.libs/ortools.dll").exists()
    assert any((win / "Lib/site-packages/numpy").rglob("*.pyd"))
    assert any((win / "Lib/site-packages/pandas").rglob("*.pyd"))
    print("OK Windows runtime structure (not executed on Windows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

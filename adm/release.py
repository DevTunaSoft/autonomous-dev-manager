"""Reproducible source release and opt-in Windows executable build planning.

Does not install dependencies or run untrusted code. Windows binaries require
an actual Windows build host and subsequent Windows runtime acceptance tests.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

EXCLUDED = {"__pycache__", ".git", ".venv", "venv", ".adm-state", ".adm-worker-state", "node_modules", ".pytest_cache"}

def source_files(root: Path):
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlinks not allowed in release source: {path}")
        if path.is_file() and not any(part in EXCLUDED for part in path.relative_to(root).parts) and path.suffix != ".pyc":
            yield path

def create_source_release(root: str | Path, destination: str | Path):
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    if not (root / "adm" / "__init__.py").is_file() or not (root / "tests").is_dir():
        raise ValueError("Expected complete ADM source and tests")
    if destination.is_relative_to(root):
        raise ValueError("Release destination must be outside the source tree")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {}
    files = list(source_files(root))
    for file in files:
        manifest[file.relative_to(root).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    payload = json.dumps({"format": "ADM-source-v1", "files": manifest}, sort_keys=True, indent=2).encode()
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".zip", delete=False) as f:
        temp = Path(f.name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                relative = file.relative_to(root).as_posix()
                info = zipfile.ZipInfo("ADM/" + relative, (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, file.read_bytes())
            info = zipfile.ZipInfo("ADM/SOURCE-MANIFEST.json", (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
        verify_source_release(temp)
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    return {"archive": str(destination), "file_count": len(files), "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}

def verify_source_release(path: str | Path):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt ZIP entry")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive entries")
        manifest = json.loads(archive.read("ADM/SOURCE-MANIFEST.json"))
        expected = manifest["files"]
        if set(names) != {"ADM/" + x for x in expected} | {"ADM/SOURCE-MANIFEST.json"}:
            raise ValueError("Source manifest and ZIP contents differ")
        for name, digest in expected.items():
            if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                raise ValueError("Unsafe manifest path")
            if hashlib.sha256(archive.read("ADM/" + name)).hexdigest() != digest:
                raise ValueError(f"Hash mismatch: {name}")
    return len(expected)

def windows_build_plan(root: str | Path, *, python_executable=None):
    root = Path(root).resolve()
    if not (root / "adm" / "daemon.py").is_file():
        raise ValueError("ADM source not found")
    interpreter = python_executable or sys.executable
    return [str(interpreter), "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", "ADM-Supervisor", "--paths", str(root), str(root / "adm" / "release_entry.py")]

def windows_desktop_build_plan(root: str | Path, *, python_executable=None):
    """Build a separate GUI executable, not the console daemon executable."""
    root = Path(root).resolve()
    if not (root / "adm" / "desktop_entry.py").is_file():
        raise ValueError("ADM desktop entrypoint not found")
    interpreter = python_executable or sys.executable
    return [str(interpreter), "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed", "--name", "ADM-Desktop", "--paths", str(root), str(root / "adm" / "desktop_entry.py")]

def build_windows_executable(root: str | Path, *, approve=False):
    if not approve:
        raise PermissionError("Building requires explicit approval")
    if os.name != "nt":
        raise RuntimeError("Windows executable must be built and tested on Windows")
    if subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True).returncode:
        raise RuntimeError("PyInstaller not installed; use approved setup process")
    return subprocess.run(windows_build_plan(root), cwd=str(Path(root).resolve()), check=True)

def main(argv=None):
    parser = argparse.ArgumentParser(description="ADM source package and Windows build plan")
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-zip")
    parser.add_argument("--windows-build-plan", action="store_true")
    parser.add_argument("--build-windows", action="store_true")
    args = parser.parse_args(argv)
    if args.source_zip:
        print(json.dumps(create_source_release(args.root, args.source_zip), indent=2))
    elif args.windows_build_plan:
        print(json.dumps(windows_build_plan(args.root), indent=2))
    elif args.build_windows:
        build_windows_executable(args.root, approve=True)
    else:
        parser.error("Choose --source-zip, --windows-build-plan or --build-windows")

if __name__ == "__main__":
    main()

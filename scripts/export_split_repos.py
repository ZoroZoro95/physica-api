#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BACKEND_DIRS = [
    "core",
    "scripts",
    "docs",
]
BACKEND_FILES = [
    "requirements.txt",
    "Procfile",
    "railway.json",
    ".env.example",
    "README.backend.md",
]
FRONTEND_FILES = [
    ".env.example",
    "README.md",
    "next.config.ts",
    "package-lock.json",
    "package.json",
    "postcss.config.mjs",
    "tsconfig.json",
    "vercel.json",
]
FRONTEND_DIRS = [
    "app",
    "components",
    "public",
    "renderer",
    "utils",
]

SKIP_DIR_NAMES = {
    ".git",
    ".next",
    ".vercel",
    "__pycache__",
    "node_modules",
    "questions/debug_reports",
    "questions/feedback_loop",
    "questions/visual_benchmarks",
    "questions/walkthrough_sync_reviews",
}
SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".sqlite",
    ".sqlite3",
    ".db",
}
SKIP_NAMES = {
    ".DS_Store",
    ".env",
    ".env.local",
    "next-env.d.ts",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export separate frontend/backend repo directories.")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "split_repos")
    parser.add_argument("--init-git", action="store_true", help="Run git init in each exported repo.")
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    frontend_out = out_dir / "frontend"
    backend_out = out_dir / "backend"
    _reset_dir(frontend_out)
    _reset_dir(backend_out)

    _export_frontend(frontend_out)
    _export_backend(backend_out)

    if args.init_git:
        _init_git(frontend_out)
        _init_git(backend_out)

    print(f"frontend={frontend_out}")
    print(f"backend={backend_out}")
    return 0


def _export_frontend(out: Path) -> None:
    source = ROOT / "frontend"
    for name in FRONTEND_FILES:
        _copy_file(source / name, out / name)
    for name in FRONTEND_DIRS:
        _copy_tree(source / name, out / name)
    (out / ".gitignore").write_text(
        "\n".join([
            "node_modules/",
            ".next/",
            ".vercel/",
            "out/",
            "next-env.d.ts",
            "*.tsbuildinfo",
            ".env",
            ".env*.local",
            ".DS_Store",
            "npm-debug.log*",
            "yarn-debug.log*",
            "",
        ]),
        encoding="utf-8",
    )


def _export_backend(out: Path) -> None:
    for name in BACKEND_DIRS:
        _copy_tree(ROOT / name, out / name)
    for name in BACKEND_FILES:
        target_name = "README.md" if name == "README.backend.md" else name
        _copy_file(ROOT / name, out / target_name)
    manifest_source = ROOT / "questions" / "manifest"
    if manifest_source.exists():
        _copy_tree(manifest_source, out / "questions" / "manifest")
    (out / ".gitignore").write_text(
        "\n".join([
            "__pycache__/",
            "*.py[cod]",
            ".env",
            ".venv/",
            "venv/",
            ".DS_Store",
            "db/*.sqlite",
            "db/*.sqlite3",
            "db/*.db",
            "questions/debug_reports/",
            "questions/feedback_loop/",
            "questions/visual_benchmarks/",
            "questions/walkthrough_sync_reviews/",
            "",
        ]),
        encoding="utf-8",
    )


def _copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    shutil.copytree(source, target, ignore=_ignore)


def _copy_file(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _ignore(directory: str, names: list[str]) -> set[str]:
    directory_path = Path(directory)
    skipped: set[str] = set()
    for name in names:
        path = directory_path / name
        rel = path.relative_to(ROOT) if path.is_absolute() and path.is_relative_to(ROOT) else Path(name)
        rel_posix = rel.as_posix()
        if name in SKIP_NAMES or rel_posix in SKIP_DIR_NAMES:
            skipped.add(name)
        elif path.is_dir() and name in SKIP_DIR_NAMES:
            skipped.add(name)
        elif any(name.endswith(suffix) for suffix in SKIP_SUFFIXES):
            skipped.add(name)
    return skipped


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _init_git(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "add", "."], cwd=path, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-m", "Initial beta split"], cwd=path, check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    raise SystemExit(main())

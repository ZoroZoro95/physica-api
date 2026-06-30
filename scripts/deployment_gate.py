#!/usr/bin/env python3
"""Run the local deployment gate for the projectile-motion app.

Default mode avoids network/provider calls. Use --include-image-batch when you
want to run the VLM image acceptance set as well.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
VISUAL_ROOT = ROOT / "questions" / "visual_benchmarks" / "smoke_visual_benchmark"

IMAGE_BATCH = [
    "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.11 PM.png",
    "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.18 PM.png",
    "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.24 PM.png",
    "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.30 PM.png",
    "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.36 PM.png",
    "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.42 PM.png",
    "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 12.41.58 PM.png",
]


@dataclass
class Check:
    name: str
    command: list[str]
    cwd: Path = ROOT
    required: bool = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deploy-readiness checks.")
    parser.add_argument("--include-image-batch", action="store_true", help="Run the VLM image acceptance batch.")
    parser.add_argument("--strict-git", action="store_true", help="Fail when git status is dirty.")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip the frontend TypeScript check.")
    parser.add_argument("--skip-visual-benchmark", action="store_true", help="Skip the rendered projectile visual benchmark gate.")
    parser.add_argument("--visual-min-score", type=float, default=4.0, help="Minimum acceptable visual verifier score.")
    args = parser.parse_args()
    os.environ.setdefault("PYTHONPYCACHEPREFIX", "/private/tmp/text23d-pycache")

    checks = [
        Check("python syntax: deploy-critical modules", [sys.executable, "-m", "py_compile", "core/main.py", "core/auth.py", "core/db.py", "core/feedback_loop.py", "core/walkthrough_sync_audit.py"]),
        Check("auth DB regression", [sys.executable, "scripts/regress_auth_db.py"]),
        Check("feedback DB regression", [sys.executable, "scripts/regress_feedback_loop_db.py"]),
        Check("question extraction normalization", [sys.executable, "scripts/regress_question_extraction_normalization.py"]),
        Check("projectile classifier regressions", [sys.executable, "scripts/regress_projectile_classifier.py"]),
        Check("projectile ad-hoc solver regressions", [sys.executable, "scripts/regress_ad_hoc_projectile.py"]),
        Check("projectile equation-plan regressions", [sys.executable, "scripts/regress_projectile_equation_plans.py"]),
        Check("animation scene spec regressions", [sys.executable, "scripts/regress_animation_scene_spec.py"]),
        Check("walkthrough sync audit regressions", [sys.executable, "scripts/regress_walkthrough_sync_audit.py"]),
        Check("projectile DPP manifest validation", [sys.executable, "scripts/validate_projectile_manifest.py"]),
        Check("landing media size", [sys.executable, "scripts/check_landing_media.py"]),
    ]
    if not args.skip_frontend:
        checks.append(Check("frontend production build", ["npm", "run", "build"], cwd=FRONTEND))
    if args.include_image_batch:
        checks.append(Check("seven-image extraction/solver acceptance", [sys.executable, "scripts/review_walkthrough_sync_batch.py", *IMAGE_BATCH]))

    print("== Deployment Gate ==")
    print(f"repo: {ROOT}")
    print()

    failures = 0
    failures += _repo_hygiene(strict=args.strict_git)
    failures += _env_hints()

    for check in checks:
        ok = _run_check(check)
        if not ok and check.required:
            failures += 1

    if not args.skip_visual_benchmark:
        failures += _run_visual_benchmark_gate(min_score=args.visual_min_score)

    if failures:
        print()
        print(f"FAIL: {failures} deployment gate issue(s).")
        return 1
    print()
    print("PASS: local deployment gate passed.")
    return 0


def _repo_hygiene(*, strict: bool) -> int:
    print("## Repo hygiene")
    result = subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        print("FAIL git status could not run")
        print(result.stderr.strip())
        return 1
    status = result.stdout.strip()
    if status:
        print(status)
        if strict:
            print("FAIL dirty git tree in --strict-git mode")
            return 1
        print("WARN dirty git tree; review before deploy")
    else:
        print("PASS clean git tree")
    print()
    return 0


def _env_hints() -> int:
    print("## Production env sanity")
    aliases = {
        "auth secret": ("APP_AUTH_SECRET", "AUTH_SECRET"),
        "feedback retry secret": ("FEEDBACK_RETRY_TOKEN", "FEEDBACK_SECRET"),
        "frontend origin": ("FRONTEND_ORIGIN", "FRONTEND_ORIGINS"),
        "frontend API URL": ("NEXT_PUBLIC_API_URL",),
        "google client": ("GOOGLE_CLIENT_ID", "NEXT_PUBLIC_GOOGLE_CLIENT_ID"),
        "llm provider key": ("GROQ_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"),
        "projectile classifier mode": ("PROJECTILE_CLASSIFIER",),
    }
    missing = []
    for label, keys in aliases.items():
        if not any(os.getenv(key) for key in keys):
            missing.append(f"{label}: {' or '.join(keys)}")
    if missing:
        print("WARN missing local env values; this is okay locally but must be set in Railway/Vercel:")
        for item in missing:
            print(f"- {item}")
    else:
        print("PASS local env aliases present")
    print()
    return 0


def _run_check(check: Check) -> bool:
    print(f"## {check.name}")
    print("$ " + " ".join(check.command))
    result = subprocess.run(check.command, cwd=check.cwd, text=True, capture_output=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode == 0:
        print("PASS")
        print()
        return True
    print(f"FAIL exit={result.returncode}")
    print()
    return False


def _run_visual_benchmark_gate(*, min_score: float) -> int:
    print("## projectile visual benchmark gate")
    port = _free_port()
    frontend_url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        ["npm", "run", "start", "--", "-H", "127.0.0.1", "-p", str(port)],
        cwd=FRONTEND,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        if not _wait_for_http(frontend_url, timeout_s=30):
            print("FAIL frontend server did not become ready for visual benchmark")
            return 1

        checks = [
            Check(
                "render all projectile benchmark beats",
                [
                    "node",
                    "scripts/render_walkthrough_sync_manifest.mjs",
                    "--frontend",
                    frontend_url,
                    "--audit-dir",
                    str(VISUAL_ROOT / "sync_audit"),
                    "--all-beats",
                    "--check-layout",
                    "--check-variation",
                    "--screenshot-dir",
                    str(VISUAL_ROOT / "screenshots"),
                    "--svg-dir",
                    str(VISUAL_ROOT / "svgs"),
                    "--visual-index-path",
                    str(VISUAL_ROOT / "visual_index.json"),
                ],
            ),
            Check(
                "build visual review queue",
                [
                    sys.executable,
                    "scripts/build_visual_review_queue.py",
                    str(VISUAL_ROOT / "visual_index.json"),
                    "--out-dir",
                    str(VISUAL_ROOT / "review_queue"),
                ],
            ),
            Check(
                "SVG beat/template contract",
                [
                    sys.executable,
                    "scripts/audit_svg_beat_contract.py",
                    "--visual-index",
                    str(VISUAL_ROOT / "visual_index.json"),
                ],
            ),
            Check(
                "visual verifier verdict threshold",
                [
                    sys.executable,
                    "scripts/validate_visual_verdicts.py",
                    "--verdicts",
                    str(VISUAL_ROOT / "review_queue" / "visual_verdicts.json"),
                    "--min-score",
                    str(min_score),
                ],
            ),
        ]
        failures = 0
        for check in checks:
            ok = _run_check(check)
            if not ok:
                failures += 1
        return failures
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        print()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(url: str, *, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _http_ok(url):
            return True
        time.sleep(0.5)
    return False


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())

# 299. Package them into a project or team plugin.
"""
plugins/network-engineering/hooks/run_post_edit_checks.py
C10 Post-Edit Hook Runner (Packaged)

Triggered by Claude Code after any Edit/Write tool call.
Reads the tool result from stdin (JSON), inspects the file path,
and runs the required checks when a Python file under spark/ or ml/ is edited.

Checks performed:
  1. Grain/duplicate check  — test_pipeline_91_92.py (TestSparkFailurePath)
  2. ML2 feature-leakage    — Phase_4/tests/test_c10_ml2_leakage.py

Exit codes:
  0  — all checks passed (or file is not in scope)
  2  — one or more checks failed (Claude Code treats non-zero as block/warn)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Repository root discovery ──────────────────────────────────────────────────
def _find_repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".git").exists() or (parent / "CLAUDE.md").exists():
            return parent
    return p.parents[3] if len(p.parents) > 3 else p.parents[-1]

REPO_ROOT = _find_repo_root()

# ── Log file ──────────────────────────────────────────────────────────────────
LOG_FILE = REPO_ROOT / "logs" / "hook_log.csv"

# ── Monitored directory prefixes (relative to repo root) ─────────────────────
WATCHED_DIRS = ("spark/", "spark\\", "ml/", "ml\\")

# ── Test commands ─────────────────────────────────────────────────────────────
GRAIN_TEST_CMD = [
    sys.executable, "-m", "pytest",
    "test_pipeline_91_92.py",
    "-k", "TestSparkFailurePath",
    "-v", "--tb=short", "--no-header",
]

ML2_TEST_CMD = [
    sys.executable, "-m", "pytest",
    "Phase_7/c_tasks/tests/test_c10_ml2_leakage.py",
    "-v", "--tb=short", "--no-header",
]

HOOK_NAME = "post-edit:spark_ml_checks"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_log(trigger_file: str, checks: str, result: str, details: str) -> None:
    """Append one row to logs/hook_log.csv."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not LOG_FILE.exists()
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        if write_header:
            fh.write("datetime,hook_name,trigger_file,checks_performed,result,details\n")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = ",".join([
            ts,
            HOOK_NAME,
            trigger_file.replace(",", ";"),
            checks.replace(",", ";"),
            result,
            details.replace(",", ";").replace("\n", " | "),
        ])
        fh.write(row + "\n")


def _run_test(cmd: list, label: str) -> tuple[bool, str]:
    """Run a pytest command; return (passed, output_summary)."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=120,
        )
        passed = proc.returncode == 0
        stdout_lines = (proc.stdout + proc.stderr).strip().splitlines()
        summary_lines = [l for l in stdout_lines if l.strip()]
        summary = summary_lines[-1] if summary_lines else "(no output)"
        return passed, summary
    except subprocess.TimeoutExpired:
        return False, f"{label}: timed out after 120s"
    except Exception as exc:  # noqa: BLE001
        return False, f"{label}: runner error — {exc}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        event = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        event = {}

    tool_input = event.get("tool_input", {})
    file_path: str = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("target_file")
        or ""
    )

    try:
        rel = Path(file_path).resolve().relative_to(REPO_ROOT)
        rel_str = str(rel).replace("\\", "/")
        is_watched = rel_str.startswith("spark/") or rel_str.startswith("ml/")
        is_python = rel_str.endswith(".py")
    except ValueError:
        is_watched = False
        is_python = False
        rel_str = file_path

    if not is_watched or not is_python:
        return 0

    print(f"\n{'='*60}")
    print(f"[C10 Hook] {HOOK_NAME}")
    print(f"[C10 Hook] Triggered by: {rel_str}")
    print(f"{'='*60}")

    checks_run = []
    all_passed = True
    all_details = []

    # ── Check 1: Grain/duplicate ──────────────────────────────────────────────
    print("\n[C10 Hook] Running Check 1: Grain/duplicate (grid_id, timestamp) ...")
    grain_passed, grain_summary = _run_test(GRAIN_TEST_CMD, "Grain check")
    checks_run.append("grain_duplicate_check")
    status1 = "PASS" if grain_passed else "FAIL"
    print(f"[C10 Hook] Grain/duplicate check: {status1}")
    if not grain_passed:
        print(f"[C10 Hook]   Reason: {grain_summary}")
        all_passed = False
        all_details.append(f"grain_check FAIL: {grain_summary}")
    else:
        all_details.append("grain_check PASS")

    # ── Check 2: ML2 feature-leakage ─────────────────────────────────────────
    print("\n[C10 Hook] Running Check 2: ML2 feature-leakage ...")
    ml2_passed, ml2_summary = _run_test(ML2_TEST_CMD, "ML2 leakage")
    checks_run.append("ml2_leakage_test")
    status2 = "PASS" if ml2_passed else "FAIL"
    print(f"[C10 Hook] ML2 leakage test:         {status2}")
    if not ml2_passed:
        print(f"[C10 Hook]   Reason: {ml2_summary}")
        all_passed = False
        all_details.append(f"ml2_leakage FAIL: {ml2_summary}")
    else:
        all_details.append("ml2_leakage PASS")

    overall = "PASS" if all_passed else "FAIL"
    print(f"\n[C10 Hook] {'='*50}")
    print(f"[C10 Hook] Overall hook: {overall}")
    print(f"[C10 Hook] {'='*50}\n")

    _write_log(
        trigger_file=rel_str,
        checks="|".join(checks_run),
        result=overall,
        details=" | ".join(all_details),
    )

    return 0 if all_passed else 2


if __name__ == "__main__":
    sys.exit(main())

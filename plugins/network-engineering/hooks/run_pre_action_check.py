# 299. Package them into a project or team plugin.
"""
plugins/network-engineering/hooks/run_pre_action_check.py
C10 Pre-Action Gate for Sensitive Pipeline Configuration (Packaged)

Triggered by Claude Code BEFORE any Edit/Write tool call.
Reads the about-to-be-edited file path from stdin (JSON).
If the file is in the sensitive list, blocks the action by exiting code 2
and writing a clear BLOCKED/APPROVAL REQUIRED message.

Sensitive paths (require explicit human confirmation before Claude edits):
  - Phase_3/AirFlow_Practice/dags/          (Airflow DAGs)
  - spark/spark_session.py                  (Spark runtime config)
  - spark/JOB_CONTRACT.md                   (Pipeline contract)
  - spark/telecom_pipeline.py               (Pipeline entry point)
  - warehouse/schema.sql                    (Database schema)
  - Phase_4/schemas.py                      (API schema — breaking-change risk)

Exit codes:
  0  — file is not sensitive, proceed
  2  — sensitive file detected, BLOCKED — Claude Code will not proceed
"""

import json
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

HOOK_NAME = "pre-action:sensitive_pipeline_gate"

# ── Sensitive path prefixes / exact names (relative to REPO_ROOT, / separated) ─
SENSITIVE_PREFIXES = [
    "Phase_3/AirFlow_Practice/dags/",
    "Phase_3/AirFlow_Practice/dags\\",
]

SENSITIVE_EXACT = {
    "spark/spark_session.py",
    "spark/JOB_CONTRACT.md",
    "spark/telecom_pipeline.py",
    "warehouse/schema.sql",
    "Phase_4/schemas.py",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_log(trigger_file: str, result: str, details: str) -> None:
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
            "sensitive_path_check",
            result,
            details.replace(",", ";"),
        ])
        fh.write(row + "\n")


def _is_sensitive(rel_str: str) -> tuple[bool, str]:
    """Return (True, reason) if the path is in the sensitive list."""
    norm = rel_str.replace("\\", "/")

    for prefix in SENSITIVE_PREFIXES:
        if norm.startswith(prefix.replace("\\", "/")):
            return True, f"Airflow DAG directory: {prefix}"

    if norm in SENSITIVE_EXACT:
        return True, f"Sensitive pipeline file: {norm}"

    return False, ""


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

    # Resolve relative to repo root
    try:
        rel = Path(file_path).resolve().relative_to(REPO_ROOT)
        rel_str = str(rel).replace("\\", "/")
    except ValueError:
        # File is outside repo root — not sensitive
        return 0

    sensitive, reason = _is_sensitive(rel_str)

    if not sensitive:
        return 0

    # ── BLOCKED ───────────────────────────────────────────────────────────────
    block_msg = (
        f"\n{'='*60}\n"
        f"[C10 Hook] {HOOK_NAME}\n"
        f"[C10 Hook] APPROVAL REQUIRED\n"
        f"{'='*60}\n"
        f"\n"
        f"  File:   {rel_str}\n"
        f"  Reason: {reason}\n"
        f"\n"
        f"  This file is classified as SENSITIVE PIPELINE CONFIGURATION\n"
        f"  under the NOPIS C6 permission policy (CLAUDE.md §11, ASK tier).\n"
        f"\n"
        f"  Claude Code has BLOCKED this edit.\n"
        f"\n"
        f"  To proceed:\n"
        f"    1. Review the proposed change yourself.\n"
        f"    2. Explicitly tell Claude: 'I approve this edit to {rel_str}.'\n"
        f"    3. Claude will then make the change under your direction.\n"
        f"\n"
        f"  This check does NOT bypass C6. It enforces the ASK tier.\n"
        f"{'='*60}\n"
    )

    print(block_msg, file=sys.stderr)
    print(f"[C10 BLOCKED] Edit to '{rel_str}' requires explicit human approval. "
          f"Reason: {reason}", flush=True)

    _write_log(
        trigger_file=rel_str,
        result="BLOCKED",
        details=f"APPROVAL REQUIRED — {reason}",
    )

    return 2


if __name__ == "__main__":
    sys.exit(main())

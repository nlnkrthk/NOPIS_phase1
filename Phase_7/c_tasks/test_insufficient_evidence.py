# C1 — Task 233: Insufficient Evidence Test.
#
# Test 1: send a complete evidence object to Claude.
# Test 2: send the SAME evidence object with anomaly_score removed entirely
#         (the key is deleted, never replaced with 0 or any other value) and
#         confirm Claude explicitly says severity cannot be determined and
#         names the missing evidence, instead of inventing a severity.
#
# Usage (from the project root):
#   python -m Phase_4.test_insufficient_evidence            # uses grid_id 5917
#   python -m Phase_4.test_insufficient_evidence 6214       # uses a different grid_id

import copy
import json
import os
import sys

try:
    from Phase_4.database import SessionLocal
    from Phase_4.services import get_evidence_object
    from Phase_7.c_tasks.claude_insight_service import generate_insight
except ModuleNotFoundError:
    try:
        from database import SessionLocal
        from services import get_evidence_object
        from claude_insight_service import generate_insight
    except ModuleNotFoundError:
        from Phase_4.database import SessionLocal
        from Phase_4.services import get_evidence_object
        from claude_insight_service import generate_insight

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

DEFAULT_GRID_ID = 5917  # a HIGH-direction anomaly, so removing anomaly_score is a real change


def run(grid_id: int = DEFAULT_GRID_ID):
    db = SessionLocal()
    try:
        evidence = get_evidence_object(db, grid_id)
    finally:
        db.close()

    if evidence is None:
        raise SystemExit(
            f"No matched grid_features + network_anomaly_scores row for grid_id={grid_id}. "
            "Pick a grid_id that has a matched row."
        )

    print("=" * 70)
    print("TEST 1 — complete evidence")
    print("=" * 70)
    print(json.dumps(evidence, indent=2))
    complete_response = generate_insight(evidence)
    print("\nClaude response:")
    print(complete_response)

    incomplete_evidence = copy.deepcopy(evidence)
    del incomplete_evidence["anomaly_score"]  # removed entirely, not zeroed

    print("\n" + "=" * 70)
    print("TEST 2 — anomaly_score removed entirely")
    print("=" * 70)
    print(json.dumps(incomplete_evidence, indent=2))
    incomplete_response = generate_insight(incomplete_evidence)
    print("\nClaude response:")
    print(incomplete_response)

    result = {
        "grid_id": grid_id,
        "test_1_complete_evidence": {
            "evidence": evidence,
            "claude_response": complete_response,
        },
        "test_2_missing_anomaly_score": {
            "evidence": incomplete_evidence,
            "claude_response": incomplete_response,
        },
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "insufficient_evidence_test.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved test results to {out_path}")
    return result


if __name__ == "__main__":
    # LLM output can contain characters outside the Windows console's default
    # cp1252 encoding (e.g. typographic spaces/dashes); print as UTF-8 instead
    # of crashing mid-run.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    requested_grid_id = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GRID_ID
    run(requested_grid_id)

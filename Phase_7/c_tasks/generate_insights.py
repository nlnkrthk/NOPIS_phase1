# C1 — Task 230 driver.
#
# Builds an evidence object (Task 229, services.get_evidence_object) for each
# of several grids, sends it to Claude (claude_insight_service.generate_insight),
# and prints/saves the evidence object plus Claude's four-section response for
# each grid.
#
# Usage (from the project root):
#   python -m Phase_4.generate_insights            # runs the 5 default grids
#   python -m Phase_4.generate_insights 1 2 3 4 5   # runs specific grid_ids

import json
import os
import sys
from datetime import datetime, timezone

try:
    from Phase_4.database import SessionLocal
    from Phase_4.services import get_evidence_object
    from Phase_7.c_tasks.claude_insight_service import generate_insight, current_model_name
except ModuleNotFoundError:
    try:
        from database import SessionLocal
        from services import get_evidence_object
        from claude_insight_service import generate_insight, current_model_name
    except ModuleNotFoundError:
        from Phase_4.database import SessionLocal
        from Phase_4.services import get_evidence_object
        from claude_insight_service import generate_insight, current_model_name

# Chosen to cover the range actually present in the data: two NORMAL grids,
# two HIGH-direction anomalies, and one LOW-direction anomaly.
DEFAULT_GRIDS = [1, 2, 5917, 6214, 1876]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def run(grid_ids):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    results = []
    db = SessionLocal()

    try:
        for grid_id in grid_ids:
            print("=" * 70)
            print(f"GRID {grid_id}")
            print("=" * 70)

            evidence = get_evidence_object(db, grid_id)
            if evidence is None:
                print(
                    f"No matched grid_features + network_anomaly_scores row for "
                    f"grid_id={grid_id}. Skipping (not fabricating data)."
                )
                print()
                continue

            print("Evidence object:")
            print(json.dumps(evidence, indent=2))

            response_text = generate_insight(evidence)
            print("\nClaude response:")
            print(response_text)
            print()

            results.append({"evidence": evidence, "claude_response": response_text})
    finally:
        db.close()

    out_path = os.path.join(OUTPUT_DIR, "insights_run.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "model": current_model_name(),
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"Saved {len(results)} evidence/response pairs to {out_path}")
    return results


if __name__ == "__main__":
    # LLM output can contain characters outside the Windows console's default
    # cp1252 encoding (e.g. typographic spaces/dashes); print as UTF-8 instead
    # of crashing mid-run.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    requested = [int(a) for a in sys.argv[1:]] or DEFAULT_GRIDS
    run(requested)

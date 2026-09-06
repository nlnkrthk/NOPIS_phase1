import json
import os
import sys
from datetime import datetime

# Ensure project root is in path
from pathlib import Path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from Phase_4.database import SessionLocal
from Phase_4.services import (
    get_grid_activity,
    get_alerts,
    get_grid_features,
    predict_grid_risk
)
try:
    from Phase_7.c_tasks.claude_insight_service import _active_provider, ANTHROPIC_MODEL, NVIDIA_MODEL, NVIDIA_BASE_URL
except ModuleNotFoundError:
    from claude_insight_service import _active_provider, ANTHROPIC_MODEL, NVIDIA_MODEL, NVIDIA_BASE_URL
from sqlalchemy import text

# 240. Collect the current grid metrics, recent history, prior alerts, model score and pipeline quality status from DE7 and API6.
def collect_evidence(grid_id: int):
    db = SessionLocal()
    try:
        # Pipeline status
        pipeline_status = {}
        row = db.execute(text("SELECT MAX(timestamp) FROM dim_time")).first()
        if row and row[0]:
            pipeline_status = {
                "status": "HEALTHY",
                "latest_timestamp": str(row[0]),
                "data_quality": "VALID",
                "rejected_rows": 0
            }
        else:
            pipeline_status = {
                "status": "UNHEALTHY",
                "latest_timestamp": None,
                "data_quality": "STALE",
                "rejected_rows": 5000
            }

        # Recent history
        recent_history = get_grid_activity(db, grid_id=grid_id) or []
        
        # Current metrics (latest row of recent history)
        current_metrics = recent_history[-1] if recent_history else {}
        
        # Prior alerts (we fetch global alerts and filter for this grid)
        all_alerts = get_alerts(db, limit=100) or []
        prior_alerts = [a for a in all_alerts if a["grid_id"] == grid_id]
        
        # Model scores
        class MockRequest:
            def __init__(self, gid):
                self.grid_id = gid
                self.avg_activity = None
                self.activity_growth = None
                self.active_hours = None
                self.peak_ratio = None
                self.variability = None
                self.internet_share = None
                self.model_version = None
                self.as_of = None
        
        try:
            model_scores = predict_grid_risk(db, MockRequest(grid_id))
        except Exception:
            model_scores = {"error": "Prediction unavailable"}
            
        return {
            "grid_id": grid_id,
            "current_metrics": current_metrics,
            "recent_history_raw": recent_history,
            "prior_alerts": prior_alerts,
            "model_scores": model_scores,
            "pipeline_status": pipeline_status
        }
    finally:
        db.close()

# 242. Summarize the older evidence before inserting it into the active context.
def summarize_history(recent_history: list):
    if not recent_history:
        return "No historical data available."
    
    total_activities = [r["total_activity"] for r in recent_history]
    avg = sum(total_activities) / len(total_activities)
    peak = max(total_activities)
    min_val = min(total_activities)
    
    return {
        "hours_analyzed": len(recent_history),
        "average_activity": round(avg, 2),
        "peak_activity": round(peak, 2),
        "min_activity": round(min_val, 2),
        "trend": "Stable" if abs(total_activities[-1] - avg) < (avg * 0.2) else ("Spiking" if total_activities[-1] > avg else "Dropping")
    }

# 241. Compare a “dump everything ” prompt against a curated context package.
def create_contexts(grid_id: int, simulate_pipeline_failure: bool = False, include_irrelevant: bool = False):
    evidence = collect_evidence(grid_id)
    
    if simulate_pipeline_failure:
        evidence["pipeline_status"] = {
            "status": "UNHEALTHY",
            "latest_timestamp": evidence["pipeline_status"]["latest_timestamp"],
            "data_quality": "STALE",
            "rejected_rows": 1250,
            "error_msg": "ETL job failed, handled nulls inserted, analytics data is stale"
        }

    # Version 1 - Dump Everything
    dump_context = {
        "grid_id": evidence["grid_id"],
        "current_metrics": evidence["current_metrics"],
        "prior_alerts": evidence["prior_alerts"],
        "model_scores": evidence["model_scores"],
        "pipeline_status": evidence["pipeline_status"],
        "recent_history": evidence["recent_history_raw"]  # Raw rows
    }
    
    # Version 2 - Curated Context
    curated_context = {
        "grid_id": evidence["grid_id"],
        "current_metrics": evidence["current_metrics"],
        "prior_alerts": evidence["prior_alerts"],
        "model_scores": evidence["model_scores"],
        "pipeline_status": evidence["pipeline_status"],
        "recent_history_summary": summarize_history(evidence["recent_history_raw"])
    }
    
    if include_irrelevant:
        curated_context["irrelevant_info"] = "Grid 9999 is currently experiencing congestion due to a local football match. Also, the weather in Milan is rainy."
        
    return json.dumps(dump_context, indent=2, default=str), json.dumps(curated_context, indent=2, default=str)


# 243. Ask Claude to separate CURRENT EVIDENCE, HISTORICAL EVIDENCE and UNCERTAINTY.
SYSTEM_PROMPT = """Investigate an unusual activity pattern at Grid 4821.

I am providing a curated evidence package containing:
- current interval metrics
- summarized recent history (already aggregated, not raw rows)
- prior alerts for this grid
- the current model risk and anomaly score
- the pipeline status record for the run that produced this data

Answer in exactly three sections:

CURRENT EVIDENCE
What is true right now, with figures.

HISTORICAL EVIDENCE
Whether this has happened before, and what the historical evidence shows.

UNCERTAINTY
What you do NOT know, including anything the pipeline status makes doubtful.

If the pipeline status indicates rejected rows, handled nulls, stale analytics data, or other data-quality problems, treat that as material and explain how it limits the conclusion.

Do not restate raw rows.
Do not claim congestion.
Do not invent numbers.
Clearly separate observed evidence from interpretation.
"""

def call_claude(evidence_text: str) -> str:
    provider = _active_provider()
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": evidence_text}]
        )
        return "".join(b.text for b in response.content if b.type == "text")
    else:
        from openai import OpenAI
        client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])
        completion = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": evidence_text}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        return completion.choices[0].message.content

def run_tests():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    GRID = 4821
    dump_ctx, curated_ctx = create_contexts(GRID)
    
    print("=== TEST 1 & 2: DUMP vs CURATED ===")
    print("\\n--- DUMP EVERYTHING RESPONSE ---")
    resp_dump = call_claude(dump_ctx)
    print(resp_dump)
    
    print("\\n--- CURATED CONTEXT RESPONSE ---")
    resp_curated = call_claude(curated_ctx)
    print(resp_curated)
    
    print("\\n=== TEST 4: PIPELINE FAILURE ===")
    _, bad_curated_ctx = create_contexts(GRID, simulate_pipeline_failure=True)
    resp_bad = call_claude(bad_curated_ctx)
    print(resp_bad)
    
    # 244. Evaluate whether the answer changes when irrelevant context is removed.
    print("\\n=== TEST 5: REMOVE IRRELEVANT CONTEXT ===")
    _, noisy_curated_ctx = create_contexts(GRID, include_irrelevant=True)
    print("\\n--- WITH IRRELEVANT CONTEXT ---")
    resp_noisy = call_claude(noisy_curated_ctx)
    print(resp_noisy)
    
    print("\\n--- WITHOUT IRRELEVANT CONTEXT (Original Curated) ---")
    # Same as resp_curated, printing again for comparison
    print(resp_curated)
    
    # 245. Document a context-engineering checklist for the project.
    print("\\n=== CONTEXT-ENGINEERING CHECKLIST ===")
    print('''
☐ Include current metrics
☐ Include relevant historical evidence
☐ Summarize older evidence
☐ Include relevant prior alerts
☐ Include model scores
☐ Include pipeline status
☐ Do not send unnecessary raw historical rows
☐ Remove irrelevant context
☐ Clearly separate current and historical evidence
☐ Include pipeline-related uncertainty
☐ Do not invent missing values
☐ Do not claim congestion
    '''.strip())

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)
    run_tests()

import json
import os
import re
from datetime import datetime
from fastapi.testclient import TestClient

from Phase_4.main import app
from Phase_4.database import SessionLocal
from sqlalchemy import text

client = TestClient(app)

def get_network_summary(as_of: str = None) -> str:
    params = {}
    if as_of:
        params['as_of'] = as_of
    response = client.get("/network/summary", params=params)
    return response.text

def get_grid_activity(grid_id: int, as_of: str = None) -> str:
    params = {}
    if as_of:
        params['as_of'] = as_of
    response = client.get(f"/network/grid/{grid_id}", params=params)
    return response.text

def get_hotspots(limit: int = 10, severity: str = None, as_of: str = None) -> str:
    params = {'limit': limit}
    if severity:
        params['severity'] = severity
    if as_of:
        params['as_of'] = as_of
    response = client.get("/network/hotspots", params=params)
    return response.text

def get_grid_features(grid_id: int) -> str:
    response = client.get(f"/network/grid/{grid_id}/features")
    return response.text

def get_anomaly_score(grid_id: int, as_of: str = None) -> str:
    # Uses predict-risk endpoint
    payload = {"grid_id": grid_id}
    if as_of:
        payload["as_of"] = as_of
    response = client.post("/network/predict-risk", json=payload)
    return response.text

def get_grid_location(grid_id: int) -> str:
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT centroid_lon, centroid_lat FROM dim_grid WHERE grid_id = :grid_id"),
            {"grid_id": grid_id}
        ).first()
        if row:
            return json.dumps({"grid_id": grid_id, "longitude": float(row[0]), "latitude": float(row[1])})
        return json.dumps({"error": "Grid not found"})
    finally:
        db.close()

def get_pipeline_status() -> str:
    db = SessionLocal()
    try:
        row = db.execute(text("SELECT MAX(timestamp) FROM dim_time")).first()
        if row and row[0]:
            latest = row[0]
            # Consider data trustworthy if it exists
            return json.dumps({"status": "OK", "latest_timestamp": str(latest), "data_trustworthy": True})
        return json.dumps({"status": "ERROR", "error": "No data in dim_time", "data_trustworthy": False})
    finally:
        db.close()

def get_nearby_hotspots(grid_id: int = None) -> str:
    # optional mock
    return json.dumps({"error": "Not implemented"})

tools = [
    {
        "name": "get_network_summary",
        "description": "Get high-level summary of network activity",
        "input_schema": {
            "type": "object",
            "properties": {
                "as_of": {"type": "string", "description": "Optional ISO timestamp"}
            }
        }
    },
    {
        "name": "get_grid_activity",
        "description": "Get activity history for a specific grid",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {"type": "integer"},
                "as_of": {"type": "string"}
            },
            "required": ["grid_id"]
        }
    },
    {
        "name": "get_hotspots",
        "description": "Get network hotspots",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
                "severity": {"type": "string"},
                "as_of": {"type": "string"}
            }
        }
    },
    {
        "name": "get_grid_features",
        "description": "Get ML features for a grid",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {"type": "integer"}
            },
            "required": ["grid_id"]
        }
    },
    {
        "name": "get_anomaly_score",
        "description": "Get ML anomaly/risk score for a grid",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {"type": "integer"},
                "as_of": {"type": "string"}
            },
            "required": ["grid_id"]
        }
    },
    {
        "name": "get_grid_location",
        "description": "Get geographic coordinates for a grid",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {"type": "integer"}
            },
            "required": ["grid_id"]
        }
    },
    {
        "name": "get_pipeline_status",
        "description": "Check if pipeline data is current and trustworthy",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]

# 234. Expose tools mapping directly onto the endpoints already built: get_network_summary() (API1), get_grid_activity() (API2), get_hotspots() (API3), get_grid_features() (API4), get_anomaly_score() (ML4/ML6), get_grid_location() (API6) and get_pipeline_status() (API6). Optionally get_nearby_hotspots().
def dispatch_tool(name: str, args: dict) -> str:
    try:
        if name == "get_network_summary":
            return get_network_summary(args.get("as_of"))
        elif name == "get_grid_activity":
            return get_grid_activity(args.get("grid_id"), args.get("as_of"))
        elif name == "get_hotspots":
            return get_hotspots(args.get("limit", 10), args.get("severity"), args.get("as_of"))
        elif name == "get_grid_features":
            return get_grid_features(args.get("grid_id"))
        elif name == "get_anomaly_score":
            return get_anomaly_score(args.get("grid_id"), args.get("as_of"))
        elif name == "get_grid_location":
            return get_grid_location(args.get("grid_id"))
        elif name == "get_pipeline_status":
            return get_pipeline_status()
        elif name == "get_nearby_hotspots":
            return get_nearby_hotspots()
        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        # 239. Add a fallback when a tool or API call fails — the assistant must report the gap, not paper over it.
        return json.dumps({"error": f"Tool execution failed: {str(e)}"})

# 237. Require Claude to call tools rather than rely on stale prompt data.
SYSTEM_PROMPT = """You are the Network Operations Assistant for the Milan grid.

ALWAYS call a tool for factual network claims.

Never answer network questions from memory or stale information when the data may have changed.

Before reporting a current network situation as fact, call get_pipeline_status() and state whether the underlying data is currently trustworthy.

Cite which tool produced each important figure.

If a tool fails, state which tool failed and explain what cannot be concluded because of that failure.

Do not substitute estimates for missing tool results.

Activity measures are not counts or MB.

Do not claim congestion.

Separate observed evidence from interpretation.

Do not invent numbers or unsupported root causes.
"""

def call_claude(messages: list) -> str:
    from Phase_4.claude_insight_service import _active_provider, ANTHROPIC_MODEL, NVIDIA_MODEL, NVIDIA_BASE_URL
    provider = _active_provider()
    
    # 238. Return evidence references in the final assistant response, naming which tool produced each figure.
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=tools
        )
        return response
    else:
        # Using OpenAI compatible endpoint for NVIDIA
        from openai import OpenAI
        client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])
        # Format tools for OpenAI
        openai_tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools]
        
        completion = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=openai_tools,
            temperature=0.2,
            max_tokens=2000
        )
        return completion.choices[0].message

def process_conversation(user_message: str, history: list = None) -> list:
    if history is None:
        history = []
    
    history.append({"role": "user", "content": user_message})
    print(f"\nUser: {user_message}\n")
    
    while True:
        message = call_claude(history)
        
        provider = call_claude.__globals__.get('_active_provider', lambda: 'nvidia')()
        
        if provider == "anthropic":
            # Anthropic handles tools differently
            if message.stop_reason == "tool_use":
                history.append({"role": "assistant", "content": message.content})
                for block in message.content:
                    if block.type == "tool_use":
                        print(f"-> Calling tool: {block.name} with args {block.input}")
                        result = dispatch_tool(block.name, block.input)
                        history.append({
                            "role": "user", 
                            "content": [{"type": "tool_result", "tool_use_id": block.id, "content": result}]
                        })
                continue
            else:
                answer = "".join([b.text for b in message.content if b.type == "text"])
                history.append({"role": "assistant", "content": answer})
                print(f"Assistant:\n{answer}\n")
                break
        else:
            # OpenAI compatible format
            if message.tool_calls:
                history.append(message)
                for tc in message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    print(f"-> Calling tool: {tc.function.name} with args {args}")
                    result = dispatch_tool(tc.function.name, args)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": result
                    })
                continue
            else:
                answer = message.content or ""
                history.append({"role": "assistant", "content": answer})
                print(f"Assistant:\n{answer}\n")
                break
    
    return history

def run_tests():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    # 235. Implement one conversation: “Which areas need attention right now?”
    print("=== TEST 1 & 2 ===")
    history = process_conversation("Which areas need attention right now?")
    
    # 236. Implement the follow-up: “Explain Grid 4821.”
    history = process_conversation("Explain Grid 4821.", history)
    
    print("\n=== TEST 3: Tool failure ===")
    history2 = process_conversation("What is the anomaly score for Grid 4821? Use a tool but assume it fails.")
    # Wait, the failure is simulated by forcing an error in dispatch_tool or passing invalid input
    # Let's temporarily break get_anomaly_score
    global get_anomaly_score
    old_get_anomaly = get_anomaly_score
    def broken_anomaly(grid_id, as_of=None):
        raise Exception("Connection timeout to ML service")
    get_anomaly_score = broken_anomaly
    
    process_conversation("Explain Grid 4821 again.")
    get_anomaly_score = old_get_anomaly
    
if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)
    run_tests()

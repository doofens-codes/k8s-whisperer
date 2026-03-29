import json
import os
from datetime import datetime
from state import ClusterState
from dotenv import load_dotenv
from ai_client import client

load_dotenv()
AUDIT_LOG = "logs/audit_log.json"

PROMPT = """
Write a 3-sentence incident report for a non-technical manager.

Incident: {anomaly_type} on pod {pod_name}
Root cause: {diagnosis}
Action taken: {action}
Result: {result}

Plain English only. No jargon. No markdown. Be specific.
"""


def explain_node(state: ClusterState) -> dict:
    print("[EXPLAIN] Writing incident report...")
    
    anomaly = state["anomalies"][0] if state["anomalies"] else {}
    plan = state.get("plan") or {}
    
    prompt = PROMPT.format(
        anomaly_type=anomaly.get("type", "Unknown"),
        pod_name=anomaly.get("affected_resource", "Unknown"),
        diagnosis=state.get("diagnosis", "Unknown"),
        action=plan.get("action", "none"),
        result=state.get("result", "none")
    )
    
    response = client.generate(prompt, model=os.getenv("LLAMA_MODEL", "llama-3.3-70b-versatile"))
    explanation = response.strip()
    
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "incident_type": anomaly.get("type", "Unknown"),
        "resource": anomaly.get("affected_resource", "Unknown"),
        "namespace": anomaly.get("namespace", "default"),
        "diagnosis": state.get("diagnosis", ""),
        "action_taken": plan.get("action", "none"),
        "blast_radius": plan.get("blast_radius", ""),
        "approved": state.get("approved", True),
        "result": state.get("result", ""),
        "explanation": explanation
    }
    
    os.makedirs("logs", exist_ok=True)
    try:
        with open(AUDIT_LOG, "r") as f:
            log = json.load(f)
    except:
        log = []
    
    log.append(entry)
    with open(AUDIT_LOG, "w") as f:
        json.dump(log, f, indent=2)
    
    print(f"[EXPLAIN] {explanation[:120]}")
    
    audit_log = state.get("audit_log", [])
    audit_log.append(entry)
    return {"audit_log": audit_log}
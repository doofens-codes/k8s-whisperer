import json
import os
from state import ClusterState
from dotenv import load_dotenv
from ai_client import client

load_dotenv()

PROMPT = """
You are a Kubernetes remediation planner.

Anomaly: {anomaly_type}
Severity: {severity}
Pod: {pod_name}
Namespace: {namespace}
Root cause: {diagnosis}

Propose a remediation action. Return ONLY valid JSON with these fields:
- action: MUST be exactly one of these strings: restart_pod, patch + 50% memory, delete_evicted, describe_pending, alert_human
- No other values allowed. No spaces, no plus signs, no variations.
- target: pod name
- namespace: namespace
- params: dict (e.g. {{"new_memory_limit": "128Mi"}} or {{}})
- confidence: float 0.0 to 1.0
- blast_radius: one of [low, medium, high]

Rules:
- CrashLoopBackOff → restart_pod, blast_radius low, confidence 0.9
- OOMKilled → patch + 50% memory, restart_pod,  blast_radius medium, confidence 0.85
- Pending → describe_pending, blast_radius low, confidence 0.9
- Evicted → delete_evicted, blast_radius low, confidence 0.95
- NodeNotReady → alert_human, blast_radius high, confidence 0.7
- DeploymentStalled → alert_human, blast_radius high, confidence 0.7

Return ONLY valid JSON. No markdown. No explanation.
"""


def plan_node(state: ClusterState) -> dict:
    print("[PLAN] Generating remediation plan...")
    
    if not state["anomalies"]:
        return {"plan": None}
    
    anomaly = state["anomalies"][0]
    
    prompt = PROMPT.format(
        anomaly_type=anomaly["type"],
        severity=anomaly["severity"],
        pod_name=anomaly["affected_resource"],
        namespace=anomaly["namespace"],
        diagnosis=state["diagnosis"]
    )
    
    raw = client.generate(prompt)
    
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    
    try:
        plan = json.loads(raw)
        print(f"[PLAN] Action: {plan['action']} | Blast: {plan['blast_radius']} | Confidence: {plan['confidence']}")
        return {"plan": plan}
    except Exception as e:
        print(f"[PLAN] Parse error: {e}")
        return {"plan": None}
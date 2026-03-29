import json
import os
from google import genai
from state import ClusterState
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PROMPT = """
You are a Kubernetes remediation planner.

Anomaly: {anomaly_type}
Severity: {severity}
Pod: {pod_name}
Namespace: {namespace}
Root cause: {diagnosis}

Propose a remediation action. Return ONLY valid JSON with these fields:
- action: one of [restart_pod, patch_memory, delete_evicted, describe_pending, alert_human]
- target: pod name
- namespace: namespace
- params: dict (e.g. {{"new_memory_limit": "128Mi"}} or {{}})
- confidence: float 0.0 to 1.0
- blast_radius: one of [low, medium, high]

Rules:
- CrashLoopBackOff → restart_pod, blast_radius low, confidence 0.9
- OOMKilled → patch_memory, blast_radius medium, confidence 0.85
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
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    raw = response.text.strip()
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
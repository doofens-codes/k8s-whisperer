import json
import os
from state import ClusterState
from dotenv import load_dotenv
from ai_client import client

load_dotenv()

PROMPT = """
You are a Kubernetes anomaly detection expert.

Analyze the following cluster state and detect any anomalies.

For each anomaly return a JSON array with objects:
- type: one of [CrashLoopBackOff, OOMKilled, Pending, ImagePullBackOff, Evicted, DeploymentStalled, NodeNotReady]
- severity: one of [CRITICAL, HIGH, MED, LOW]
- affected_resource: exact pod name
- namespace: kubernetes namespace
- confidence: float 0.0 to 1.0

Rules:
- CrashLoopBackOff: waiting_reason = CrashLoopBackOff OR restart_count > 3
- OOMKilled: terminated_reason = OOMKilled
- Pending: phase = Pending
- ImagePullBackOff: waiting_reason = ImagePullBackOff or ErrImagePull
- Evicted: reason = Evicted
- Ignore pods in kube-system namespace
- If cluster is healthy return empty array []

Return ONLY a valid JSON array. No markdown. No explanation.

Cluster state:
{state}
"""


def detect_node(state: ClusterState) -> dict:
    print("[DETECT] Running anomaly detection...")
    
    events_str = json.dumps(state["events"], indent=2)
    prompt = PROMPT.format(state=events_str)
    
    response = client.generate(prompt, model=os.getenv("LLAMA_MODEL", "llama-3.3-70b-versatile"))
    raw = response.strip()
    
    # Strip markdown if model adds it
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    
    try:
        anomalies_data = json.loads(raw)
        print(f"[DETECT] Found {len(anomalies_data)} anomalies")
        return {"anomalies": anomalies_data}
    except Exception as e:
        print(f"[DETECT] Parse error: {e} | Raw: {raw[:200]}")
        return {"anomalies": []}
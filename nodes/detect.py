import json
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
- If a pod shows both OOMKilled and CrashLoopBackOff, report ONLY OOMKilled
- One anomaly object per pod maximum.

Return ONLY a valid JSON array. No markdown. No explanation.

Cluster state:
{state}
"""


def detect_node(state: ClusterState) -> dict:
    print("[DETECT] Running anomaly detection...")

    events_str = json.dumps(state["events"], indent=2)
    prompt = PROMPT.format(state=events_str)

    raw = client.generate(prompt)

    # Clean LLM output
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        anomalies_data = json.loads(raw)
    except Exception as e:
        print(f"[DETECT] Parse error: {e} | Raw: {raw[:200]}")
        return {"anomalies": []}

    # -------------------------------
    # 🔧 FIX 1: Remove false OOM (Running pods)
    # -------------------------------
    pod_lookup = {
        p["name"]: p for p in state["events"] if "name" in p
    }

    filtered = []
    for a in anomalies_data:
        pod_name = a["affected_resource"]
        pod = pod_lookup.get(pod_name, {})

        if (
            a["type"] == "OOMKilled"
            and pod.get("phase") == "Running"
        ):
            continue

        filtered.append(a)

    # -------------------------------
    # 🔧 FIX 2: OOM > CrashLoop priority
    # -------------------------------
    final = []
    seen = set()

    for a in filtered:
        pod = a["affected_resource"]

        if pod in seen:
            continue

        # If OOM exists for this pod → ignore CrashLoop
        has_oom = any(
            x["affected_resource"] == pod and x["type"] == "OOMKilled"
            for x in filtered
        )

        if has_oom and a["type"] == "CrashLoopBackOff":
            continue

        final.append(a)
        seen.add(pod)

    print(f"[DETECT] Found {len(final)} anomalies")
    return {"anomalies": final}
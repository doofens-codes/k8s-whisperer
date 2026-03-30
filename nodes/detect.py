import json
from state import ClusterState
from dotenv import load_dotenv
from ai_client import client

load_dotenv()

SYSTEM = """You are an expert Kubernetes SRE diagnosing production cluster failures.
Reason from the data only. Never invent pod names or anomalies not evidenced below."""

PROMPT = """Analyze this Kubernetes cluster snapshot and return every anomaly found.

For each anomaly return a JSON object with:
- type: CrashLoopBackOff | OOMKilled | Pending | ImagePullBackOff | Evicted | DeploymentStalled | NodeNotReady | or a short novel label
- severity: CRITICAL | HIGH | MED | LOW
- affected_resource: exact pod/node name from the data
- namespace: kubernetes namespace
- confidence: float 0.0–1.0
- reasoning: one sentence citing the specific field that triggered this

Rules:
- CrashLoopBackOff: waiting_reason=CrashLoopBackOff OR restart_count>3
- OOMKilled: terminated_reason=OOMKilled AND phase!=Running
- Pending: phase=Pending
- ImagePullBackOff: waiting_reason=ImagePullBackOff or ErrImagePull
- Evicted: reason=Evicted
- NodeNotReady: node ready=False
- If same pod has both OOMKilled and CrashLoopBackOff signals → report OOMKilled only
- One entry per pod/node max. Skip kube-system namespace. Return [] if healthy.

Cluster snapshot:
{state}

Return ONLY a valid JSON array. No markdown. No explanation."""


def _slim_events(events: list) -> list:
    """
    Strip each pod/event dict down to only the fields the detector needs.
    Cuts token usage by ~80% on a typical cluster.
    """
    slim = []
    for item in events:
        if not isinstance(item, dict):
            continue

        # Pod record (has 'phase' field)
        if "phase" in item:
            slim.append({
                "name": item.get("name", ""),
                "namespace": item.get("namespace", ""),
                "phase": item.get("phase", ""),
                "reason": item.get("reason", ""),
                "waiting_reason": item.get("waiting_reason", ""),
                "terminated_reason": item.get("terminated_reason", ""),
                "last_terminated_reason": item.get("last_terminated_reason", ""),
                "restart_count": item.get("restart_count", 0),
                "pending_minutes": item.get("pending_minutes", 0),
                "ready": item.get("ready", False),
            })
        # Node record (has 'ready' but no 'phase')
        elif "ready" in item and "cpu_capacity" in item:
            slim.append({
                "name": item.get("name", ""),
                "kind": "Node",
                "ready": item.get("ready", ""),
                "memory_pressure": item.get("memory_pressure", ""),
                "disk_pressure": item.get("disk_pressure", ""),
                "unschedulable": item.get("unschedulable", False),
            })
        # Event record (has 'reason' and 'message' but no 'phase')
        elif "message" in item and "object" in item:
            # Only include Warning events — Normal events are noise for detection
            if item.get("type") == "Warning":
                slim.append({
                    "kind": "Event",
                    "reason": item.get("reason", ""),
                    "message": item.get("message", "")[:120],  # cap long messages
                    "object": item.get("object", ""),
                    "count": item.get("count", 1),
                })

    return slim


def detect_node(state: ClusterState) -> dict:
    print("[DETECT] Running anomaly detection...")

    slim = _slim_events(state["events"])
    # Compact JSON — no indent, saves ~25% tokens vs indent=2
    events_str = json.dumps(slim)

    print(f"[DETECT] Sending {len(slim)} items, ~{len(events_str)//4} tokens to LLM")

    raw = client.generate(
        prompt=PROMPT.format(state=events_str),
        system=SYSTEM
    )

    # Strip markdown fences if present
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                raw = part
                break

    raw = raw.strip()

    try:
        anomalies_data = json.loads(raw)
    except Exception as e:
        print(f"[DETECT] Parse error: {e} | Raw: {raw[:300]}")
        return {"anomalies": []}

    # Build pod lookup for post-filtering (from original events, not slim)
    pod_lookup = {
        p["name"]: p for p in state["events"]
        if isinstance(p, dict) and "phase" in p
    }

    # Filter false OOMKilled on currently-Running pods
    filtered = []
    for a in anomalies_data:
        pod_name = a.get("affected_resource", "")
        pod = pod_lookup.get(pod_name, {})
        if a.get("type") == "OOMKilled" and pod.get("phase") == "Running":
            print(f"[DETECT] Skipping false OOM on running pod {pod_name}")
            continue
        filtered.append(a)

    # OOMKilled > CrashLoopBackOff priority for same pod
    final = []
    seen = set()
    for a in filtered:
        pod = a.get("affected_resource", "")
        if pod in seen:
            continue
        has_oom = any(
            x.get("affected_resource") == pod and x.get("type") == "OOMKilled"
            for x in filtered
        )
        if has_oom and a.get("type") == "CrashLoopBackOff":
            continue
        final.append(a)
        seen.add(pod)

    print(f"[DETECT] Found {len(final)} anomalies")
    for a in final:
        print(f"  → [{a.get('severity')}] {a.get('type')} on {a.get('affected_resource')} "
              f"(conf={a.get('confidence')}) — {a.get('reasoning', '')}")

    return {"anomalies": final}
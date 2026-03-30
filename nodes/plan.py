import json
from state import ClusterState
from dotenv import load_dotenv
from ai_client import client

load_dotenv()

SYSTEM = """You are a Kubernetes remediation planner.
You reason carefully about the safest, most effective action to resolve an incident.
You consider blast radius — how many workloads could be disrupted — and always prefer the least invasive action that will actually fix the problem.
You never recommend deleting namespaces, draining nodes, or any action that would cause broad service disruption unless absolutely necessary."""

PROMPT = """Plan a remediation action for the following Kubernetes incident.

Anomaly type: {anomaly_type}
Severity: {severity}
Affected pod: {pod_name}
Namespace: {namespace}

Root cause analysis:
{diagnosis}

OFFICIAL ANOMALY -> ACTION MAPPING (STRICTLY REQUIRED):
1. CrashLoopBackOff: You MUST output "action": "restart_pod", "confidence": >0.8, "blast_radius": "low"
2. OOMKilled: You MUST output "action": "patch_memory", "confidence": >0.8, "blast_radius": "low"
3. Pending: You MUST output "action": "alert_human", "confidence": 0.5
4. ImagePullBackOff or ErrImagePull: You MUST output "action": "alert_human", "confidence": 0.5
5. Evicted: You MUST output "action": "delete_evicted", "confidence": >0.8, "blast_radius": "low"
6. Deployment Stalled: You MUST output "action": "alert_human", "confidence": 0.5
7. NodeNotReady: You MUST output "action": "alert_human", "confidence": 0.5

GLOBAL SAFETY RULES:
- If action is "alert_human", you MUST set confidence < 0.8 (e.g. 0.5) to ensure it triggers HITL routing.
- Auto-execute only happens if confidence > 0.8 and blast_radius is "low".

Return ONLY valid JSON with these exact fields:
{{
  "action": one of [restart_pod, patch_memory, delete_evicted, alert_human],
  "target": "{pod_name}",
  "namespace": "{namespace}",
  "params": {{}},
  "confidence": float 0.0–1.0,
  "blast_radius": one of [low, medium, high],
  "reasoning": "one sentence explaining why you chose this action"
}}

No markdown. No explanation outside the JSON."""


def plan_node(state: ClusterState) -> dict:
    print("[PLAN] Reasoning about remediation...")

    if not state["anomalies"]:
        return {"plan": None}

    anomaly = state["anomalies"][0]

    prompt = PROMPT.format(
        anomaly_type=anomaly.get("type", "Unknown"),
        severity=anomaly.get("severity", "UNKNOWN"),
        pod_name=anomaly.get("affected_resource", ""),
        namespace=anomaly.get("namespace", "default"),
        diagnosis=state.get("diagnosis", "No diagnosis available.")
    )

    raw = client.generate(prompt, system=SYSTEM)

    # Strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break

    raw = raw.strip()

    # Extract just the JSON object if there's surrounding text
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    try:
        plan = json.loads(raw)

        # Normalise action field — handle legacy "patch + 50% memory" style
        action = plan.get("action", "")
        if "patch" in action.lower() and "memory" in action.lower():
            plan["action"] = "patch_memory"

        print(f"[PLAN] Action: {plan['action']} | Blast: {plan['blast_radius']} | "
              f"Confidence: {plan['confidence']}")
        print(f"[PLAN] Reasoning: {plan.get('reasoning', 'none')}")
        return {"plan": plan}

    except Exception as e:
        print(f"[PLAN] Parse error: {e} | Raw: {raw[:300]}")
        return {"plan": None}
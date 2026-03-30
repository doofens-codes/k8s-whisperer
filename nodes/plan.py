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

Available actions and when to use them:
- restart_pod: delete the pod so it restarts fresh. Use for CrashLoopBackOff, transient errors, config reloads.
- patch_memory: increase the deployment's memory limit by 50%. Use for OOMKilled pods.
- delete_evicted: delete an evicted pod to clean up. Use for Evicted pods.
- describe_pending: gather describe output to understand scheduling failure. Use for Pending pods.
- alert_human: escalate to a human. Use for NodeNotReady, DeploymentStalled, or anything requiring judgment beyond pod-level operations.

Think through:
1. What action will actually fix this based on the root cause?
2. What is the blast radius — will this affect other pods, services, or users?
3. How confident are you this will resolve the issue?

Return ONLY valid JSON with these exact fields:
{{
  "action": one of [restart_pod, patch_memory, delete_evicted, describe_pending, alert_human],
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
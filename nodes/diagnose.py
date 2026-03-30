import os
from state import ClusterState
from kubectl_tools import get_pod_logs, describe_pod
from dotenv import load_dotenv
from ai_client import client

load_dotenv()

# Hard char budgets (1 token ≈ 4 chars)
# Free tier llama-3.1-8b-instant: 6000 TPM
# System+prompt overhead ~300 tokens → ~5700 left for content (~22800 chars)
# Split: 1200 describe + 1800 logs = 3000 chars = ~750 tokens — very safe
MAX_DESCRIBE_CHARS = 1200
MAX_LOGS_CHARS = 1800

SYSTEM = """You are a senior Kubernetes SRE doing root cause analysis.
Reason from evidence only. Cite specific values, error messages, and field names.
Be concise — max 120 words."""

PROMPT = """Root cause analysis for a Kubernetes incident.

Anomaly: {anomaly_type}
Pod: {pod_name} | Namespace: {namespace}
Detection signal: {detection_reasoning}

kubectl describe (truncated):
{describe}

Pod logs (recent):
{logs}

Identify: (1) precise root cause, (2) specific evidence from above, (3) whether intervention is needed.
Plain English. No bullet points. No markdown. Max 120 words."""


def diagnose_node(state: ClusterState) -> dict:
    print("[DIAGNOSE] Performing root cause analysis...")

    if not state["anomalies"]:
        return {"diagnosis": "No anomalies detected — cluster appears healthy."}

    anomaly = state["anomalies"][0]
    name = anomaly.get("affected_resource", "")
    namespace = anomaly.get("namespace", "default")
    detection_reasoning = anomaly.get("reasoning", "No detection reasoning provided.")

    logs = get_pod_logs(namespace, name)
    desc = describe_pod(namespace, name)

    # Hard-cap to stay well under token budget
    logs_trimmed = logs[-MAX_LOGS_CHARS:] if len(logs) > MAX_LOGS_CHARS else logs
    desc_trimmed = desc[:MAX_DESCRIBE_CHARS] if len(desc) > MAX_DESCRIBE_CHARS else desc

    print(f"[DIAGNOSE] logs={len(logs_trimmed)} chars, desc={len(desc_trimmed)} chars, "
          f"~{(len(logs_trimmed) + len(desc_trimmed)) // 4} tokens")

    prompt = PROMPT.format(
        anomaly_type=anomaly.get("type", "Unknown"),
        pod_name=name,
        namespace=namespace,
        detection_reasoning=detection_reasoning,
        describe=desc_trimmed,
        logs=logs_trimmed
    )

    diagnosis = client.generate(prompt, system=SYSTEM)
    print(f"[DIAGNOSE] {diagnosis[:150]}...")
    return {"diagnosis": diagnosis}
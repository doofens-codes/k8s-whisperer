import os
from google import genai
from state import ClusterState
from kubectl_tools import get_pod_logs, describe_pod
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PROMPT = """
You are a Kubernetes SRE performing root cause analysis.

Anomaly: {anomaly_type}
Pod: {pod_name}
Namespace: {namespace}

Pod description:
{describe}

Pod logs:
{logs}

Write a root cause analysis in plain English.
Be specific. Cite evidence from logs and description.
Maximum 100 words. No bullet points. No markdown.
"""


def diagnose_node(state: ClusterState) -> dict:
    if not state["anomalies"]:
        return {"diagnosis": "No anomalies detected"}
    
    print("[DIAGNOSE] Analyzing root cause...")
    
    if not state["anomalies"]:
        return {"diagnosis": "No anomalies to diagnose"}
    
    anomaly = state["anomalies"][0]
    name = anomaly["affected_resource"]
    namespace = anomaly["namespace"]
    
    logs = get_pod_logs(namespace, name)
    desc = describe_pod(namespace, name)
    
    prompt = PROMPT.format(
        anomaly_type=anomaly["type"],
        pod_name=name,
        namespace=namespace,
        describe=desc,
        logs=logs
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    diagnosis = response.text.strip()
    print(f"[DIAGNOSE] {diagnosis[:120]}...")
    return {"diagnosis": diagnosis}
import subprocess
import json


def get_all_pods() -> list:
    result = subprocess.run(
        ["kubectl", "get", "pods", "-A", "-o", "json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[KUBECTL] Error: {result.stderr}")
        return []
    data = json.loads(result.stdout)
    pods = []
    for pod in data.get("items", []):
        status = pod.get("status", {})
        container_statuses = status.get("containerStatuses", [])
        waiting_reason = ""
        terminated_reason = ""
        restart_count = 0
        if container_statuses:
            cs = container_statuses[0]
            restart_count = cs.get("restartCount", 0)
            state = cs.get("state", {})
            if "waiting" in state:
                waiting_reason = state["waiting"].get("reason", "")
            if "terminated" in state:
                terminated_reason = state["terminated"].get("reason", "")
            last_state = cs.get("lastState", {})
            if "terminated" in last_state:
                terminated_reason = last_state["terminated"].get("reason", terminated_reason)
        pods.append({
            "name": pod["metadata"]["name"],
            "namespace": pod["metadata"]["namespace"],
            "phase": status.get("phase", "Unknown"),
            "reason": status.get("reason", ""),
            "waiting_reason": waiting_reason,
            "terminated_reason": terminated_reason,
            "restart_count": restart_count,
            "conditions": status.get("conditions", [])
        })
    return pods


def get_events(namespace: str = "default") -> list:
    result = subprocess.run(
        ["kubectl", "get", "events", "-n", namespace,
         "--sort-by=.lastTimestamp", "-o", "json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    data = json.loads(result.stdout)
    events = []
    for e in data.get("items", [])[-20:]:
        events.append({
            "reason": e.get("reason", ""),
            "message": e.get("message", ""),
            "object": e.get("involvedObject", {}).get("name", ""),
            "type": e.get("type", "")
        })
    return events


def get_pod_logs(namespace: str, pod_name: str) -> str:
    result = subprocess.run(
        ["kubectl", "logs", pod_name, "-n", namespace, "--tail=100"],
        capture_output=True, text=True
    )
    output = result.stdout or result.stderr
    return output[:3000]


def describe_pod(namespace: str, pod_name: str) -> str:
    result = subprocess.run(
        ["kubectl", "describe", "pod", pod_name, "-n", namespace],
        capture_output=True, text=True
    )
    return result.stdout[:3000]


def delete_pod(namespace: str, pod_name: str) -> str:
    result = subprocess.run(
        ["kubectl", "delete", "pod", pod_name, "-n", namespace],
        capture_output=True, text=True
    )
    return result.stdout or result.stderr


def patch_memory(namespace: str, pod_name: str, new_limit: str) -> str:
    patch = json.dumps([{
        "op": "replace",
        "path": "/spec/containers/0/resources/limits/memory",
        "value": new_limit
    }])
    result = subprocess.run(
        ["kubectl", "patch", "pod", pod_name, "-n", namespace,
         "--type", "json", "-p", patch],
        capture_output=True, text=True
    )
    return result.stdout or result.stderr


def verify_pod(namespace: str, pod_name: str) -> str:
    result = subprocess.run(
        ["kubectl", "get", "pod", pod_name, "-n", namespace],
        capture_output=True, text=True
    )
    return result.stdout or result.stderr
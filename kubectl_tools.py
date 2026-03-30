import subprocess
import json
import re
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: list[str]) -> tuple[int, str, str]:
    """Run a kubectl command. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def _age_minutes(timestamp_str: str) -> float:
    """Return how many minutes ago an ISO8601 timestamp was. Returns 0 on parse failure."""
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - ts
        return delta.total_seconds() / 60
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Pod observation
# ─────────────────────────────────────────────────────────────────────────────

def get_all_pods() -> list:
    """
    Returns a normalised list of pod dicts across all namespaces.
    Each dict contains enough signal for the LLM detector to reason from.
    """
    rc, stdout, stderr = _run(["kubectl", "get", "pods", "-A", "-o", "json"])
    if rc != 0:
        print(f"[KUBECTL] get pods error: {stderr[:200]}")
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        print(f"[KUBECTL] JSON parse error: {e}")
        return []

    pods = []
    for pod in data.get("items", []):
        meta = pod.get("metadata", {})
        status = pod.get("status", {})
        container_statuses = status.get("containerStatuses", [])
        init_statuses = status.get("initContainerStatuses", [])

        waiting_reason = ""
        terminated_reason = ""
        last_terminated_reason = ""
        last_exit_code = None
        restart_count = 0
        ready = False
        container_name = ""

        if container_statuses:
            cs = container_statuses[0]
            container_name = cs.get("name", "")
            restart_count = cs.get("restartCount", 0)
            ready = cs.get("ready", False)
            state = cs.get("state", {})

            if "waiting" in state:
                waiting_reason = state["waiting"].get("reason", "")
            if "terminated" in state:
                terminated_reason = state["terminated"].get("reason", "")
                last_exit_code = state["terminated"].get("exitCode")

            last_state = cs.get("lastState", {})
            if "terminated" in last_state:
                last_terminated_reason = last_state["terminated"].get("reason", "")
                if last_exit_code is None:
                    last_exit_code = last_state["terminated"].get("exitCode")
                # For OOMKill detection: only surface if pod is NOT currently Running
                if status.get("phase") != "Running" and not terminated_reason:
                    terminated_reason = last_terminated_reason

        # Check init containers for ImagePullBackOff / other init failures
        init_waiting_reason = ""
        if init_statuses:
            ics = init_statuses[0]
            init_state = ics.get("state", {})
            if "waiting" in init_state:
                init_waiting_reason = init_state["waiting"].get("reason", "")

        # Pending age — useful for detecting pods stuck pending > N minutes
        start_time = meta.get("creationTimestamp", "")
        pending_minutes = (
            _age_minutes(start_time)
            if status.get("phase") == "Pending"
            else 0.0
        )

        pods.append({
            "name": meta.get("name", ""),
            "namespace": meta.get("namespace", ""),
            "phase": status.get("phase", "Unknown"),
            "reason": status.get("reason", ""),          # "Evicted" lives here
            "message": status.get("message", ""),        # eviction message
            "waiting_reason": waiting_reason,
            "terminated_reason": terminated_reason,
            "last_terminated_reason": last_terminated_reason,
            "last_exit_code": last_exit_code,
            "init_waiting_reason": init_waiting_reason,
            "restart_count": restart_count,
            "ready": ready,
            "container_name": container_name,            # needed for patch_memory
            "pending_minutes": round(pending_minutes, 1),
            "conditions": status.get("conditions", []),
            "start_time": start_time,
        })

    return pods


# ─────────────────────────────────────────────────────────────────────────────
# Node observation
# ─────────────────────────────────────────────────────────────────────────────

def get_nodes() -> list:
    """
    Returns node health snapshots. Includes Ready condition, memory/disk pressure,
    and resource capacity. Used to detect NodeNotReady and inform Pending diagnosis.
    """
    rc, stdout, stderr = _run(["kubectl", "get", "nodes", "-o", "json"])
    if rc != 0:
        print(f"[KUBECTL] get nodes error: {stderr[:200]}")
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []

    nodes = []
    for node in data.get("items", []):
        meta = node.get("metadata", {})
        status = node.get("status", {})
        conditions = status.get("conditions", [])

        condition_map = {c["type"]: c["status"] for c in conditions}
        ready = condition_map.get("Ready", "Unknown")
        memory_pressure = condition_map.get("MemoryPressure", "Unknown")
        disk_pressure = condition_map.get("DiskPressure", "Unknown")
        pid_pressure = condition_map.get("PIDPressure", "Unknown")

        capacity = status.get("capacity", {})
        allocatable = status.get("allocatable", {})

        nodes.append({
            "name": meta.get("name", ""),
            "ready": ready,                      # "True" | "False" | "Unknown"
            "memory_pressure": memory_pressure,
            "disk_pressure": disk_pressure,
            "pid_pressure": pid_pressure,
            "cpu_capacity": capacity.get("cpu", ""),
            "memory_capacity": capacity.get("memory", ""),
            "cpu_allocatable": allocatable.get("cpu", ""),
            "memory_allocatable": allocatable.get("memory", ""),
            "unschedulable": node.get("spec", {}).get("unschedulable", False),
            "labels": meta.get("labels", {}),    # includes node selectors like disktype=ssd
        })

    return nodes


# ─────────────────────────────────────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────────────────────────────────────

def get_events(namespace: str = "default") -> list:
    """
    Returns the 30 most recent events from a namespace, normalised.
    Includes Warning events prominently — these carry the most signal.
    """
    rc, stdout, _ = _run([
        "kubectl", "get", "events",
        "-n", namespace,
        "--sort-by=.lastTimestamp",
        "-o", "json"
    ])
    if rc != 0:
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []

    events = []
    items = data.get("items", [])

    # Take last 30, prioritising Warning type
    warnings = [e for e in items if e.get("type") == "Warning"]
    normals = [e for e in items if e.get("type") != "Warning"]
    ordered = warnings[-20:] + normals[-10:]

    for e in ordered:
        events.append({
            "reason": e.get("reason", ""),
            "message": e.get("message", ""),
            "object": e.get("involvedObject", {}).get("name", ""),
            "object_kind": e.get("involvedObject", {}).get("kind", ""),
            "type": e.get("type", ""),           # "Warning" | "Normal"
            "count": e.get("count", 1),
            "first_time": e.get("firstTimestamp", ""),
            "last_time": e.get("lastTimestamp", ""),
        })

    return events


# ─────────────────────────────────────────────────────────────────────────────
# Log retrieval with smart chunking
# ─────────────────────────────────────────────────────────────────────────────

def get_pod_logs(namespace: str, pod_name: str, tail: int = 150) -> str:
    """
    Fetches pod logs with smart chunking:
    - Tries --previous first for crashed containers (most useful for OOM/crash diagnosis)
    - Falls back to current logs
    - Strips blank lines and known-noisy patterns
    - Returns at most ~3000 chars, keeping the TAIL (most recent errors)
    """
    MAX_CHARS = 3000

    def _fetch(previous: bool = False) -> str:
        cmd = ["kubectl", "logs", pod_name, "-n", namespace, f"--tail={tail}"]
        if previous:
            cmd.append("--previous")
        rc, stdout, stderr = _run(cmd)
        return (stdout or stderr).strip()

    # Try previous logs first (crash context)
    logs = _fetch(previous=True)
    if not logs or "previous terminated container" in logs.lower():
        logs = _fetch(previous=False)

    if not logs:
        return "[No logs available]"

    # Strip excessive blank lines
    logs = re.sub(r'\n{3,}', '\n\n', logs)

    # Keep the tail — most recent output is most relevant for diagnosis
    if len(logs) > MAX_CHARS:
        logs = "...[truncated]...\n" + logs[-MAX_CHARS:]

    return logs


# ─────────────────────────────────────────────────────────────────────────────
# Pod describe
# ─────────────────────────────────────────────────────────────────────────────

def describe_pod(namespace: str, pod_name: str) -> str:
    rc, stdout, stderr = _run(["kubectl", "describe", "pod", pod_name, "-n", namespace])
    output = stdout or stderr
    # Truncate keeping the start — Events section at the bottom is the most useful
    # So we keep first 1500 chars (spec/status) + last 1500 chars (events)
    if len(output) > 3000:
        return output[:1500] + "\n...[middle truncated]...\n" + output[-1500:]
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Remediation actions
# ─────────────────────────────────────────────────────────────────────────────

def delete_pod(namespace: str, pod_name: str) -> str:
    rc, stdout, stderr = _run(["kubectl", "delete", "pod", pod_name, "-n", namespace])
    return stdout or stderr


def patch_memory(namespace: str, pod_name: str, new_limit: str) -> str:
    """
    Patches the memory limit on the deployment that owns this pod.
    Discovers the container name dynamically instead of hardcoding 'memory-hog'.
    """
    # Derive deployment name by stripping the last two hash segments (replicaset + pod)
    parts = pod_name.split("-")
    deploy_name = "-".join(parts[:-2])

    # Discover the actual container name from the live deployment spec
    rc, stdout, _ = _run([
        "kubectl", "get", "deployment", deploy_name,
        "-n", namespace, "-o", "json"
    ])
    container_name = "app"  # safe fallback
    if rc == 0:
        try:
            spec_containers = (
                json.loads(stdout)
                ["spec"]["template"]["spec"]["containers"]
            )
            if spec_containers:
                container_name = spec_containers[0]["name"]
        except Exception:
            pass

    print(f"[KUBECTL] Patching deployment '{deploy_name}' container '{container_name}' → {new_limit}")

    patch = json.dumps({
        "spec": {
            "template": {
                "spec": {
                    "containers": [{
                        "name": container_name,
                        "resources": {
                            "limits": {"memory": new_limit},
                            "requests": {"memory": new_limit}
                        }
                    }]
                }
            }
        }
    })

    rc, stdout, stderr = _run([
        "kubectl", "patch", "deployment", deploy_name,
        "-n", namespace, "--type", "merge", "-p", patch
    ])
    return stdout or stderr or f"deployment.apps/{deploy_name} patched → {new_limit}"


def verify_pod(namespace: str, pod_name: str) -> str:
    rc, stdout, stderr = _run(["kubectl", "get", "pod", pod_name, "-n", namespace])
    return stdout or stderr


def get_deployment_status(namespace: str, deploy_name: str) -> str:
    """Used by execute to verify after a patch."""
    rc, stdout, stderr = _run([
        "kubectl", "get", "deployment", deploy_name, "-n", namespace
    ])
    return stdout or stderr
import subprocess
import time
from state import ClusterState
from kubectl_tools import delete_pod, patch_memory, verify_pod, describe_pod
import json


def execute_node(state: ClusterState) -> dict:
    plan = state.get("plan")
    
    if not plan:
        return {"result": "No plan to execute"}
    
    # Check HITL decision — if came through HITL and rejected, skip
    if state.get("approved") == False:
        return {"result": "Action rejected by human"}
    
    action = plan["action"]
    target = plan["target"]
    namespace = plan["namespace"]
    params = plan.get("params", {})
    
    print(f"[EXECUTE] Running: {action} on {target}")
    print(f"[DEBUG] action='{action}' | lower='{action.lower()}'")
    result = ""
    
    if action == "restart_pod":
        result = delete_pod(namespace, target)
    
    elif "patch" in action.lower() and "memory" in action.lower():
        # Get current deployment memory from cluster
        parts = target.split("-")
        deploy_name = "-".join(parts[:-2])

        get_cmd = subprocess.run(
            ["kubectl", "get", "deployment", deploy_name, "-n", namespace, "-o", "json"],
            capture_output=True, text=True
        )

        try:
            data = json.loads(get_cmd.stdout)
            current_limit = data["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["memory"]
        except:
            current_limit = "32Mi"  # fallback

        # Convert Mi → int
        value = int(current_limit.replace("Mi", ""))

        # Increase 50%
        new_value = int(value * 1.5)

        # Cap (demo safety)
        if new_value > 128:
            new_value = 128

        limit = f"{new_value}Mi"

        print(f"[DEBUG] Scaling memory: {value}Mi → {limit}")

        result = patch_memory(namespace, target, limit)
    
    elif action == "delete_evicted":
        result = delete_pod(namespace, target)
    
    elif action == "describe_pending":
        result = describe_pod(namespace, target)
    
    elif action == "alert_human":
        result = f"[ALERT] Human notified for {target} — manual intervention required"
    
    # Verify after 30s
    print(f"[EXECUTE] Waiting 30s to verify recovery...")
    time.sleep(30)

    if "patch" in action.lower() and "memory" in action.lower():
        # Verify deployment not pod — pod name changes after patch
        parts = target.split("-")
        deploy_name = "-".join(parts[:-2])
        verify_result = subprocess.run(
            ["kubectl", "get", "deployment", deploy_name, "-n", namespace],
            capture_output=True, text=True
        )
        verify = verify_result.stdout or verify_result.stderr
    else:
        verify = verify_pod(namespace, target)

    result += f"\n[VERIFY] {verify}"
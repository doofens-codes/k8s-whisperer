import subprocess
import time
from state import ClusterState
from kubectl_tools import delete_pod, patch_memory, verify_pod, describe_pod
import json


def execute_node(state: ClusterState) -> dict:
    plan = state.get("plan")

    if not plan:
        return {"result": "No plan to execute"}

    if state.get("approved") == False:
        return {"result": "Action rejected by human — no changes made"}

    action = plan["action"]
    target = plan["target"]
    namespace = plan["namespace"]

    print(f"[EXECUTE] Running: {action} on {target} in {namespace}")

    result = ""

    if action == "restart_pod":
        result = delete_pod(namespace, target)

    elif action == "patch_memory":
        # Read current limit from deployment
        parts = target.split("-")
        deploy_name = "-".join(parts[:-2])

        print(f"[EXECUTE] Fetching current memory limit for deployment: {deploy_name}")
        get_cmd = subprocess.run(
            ["kubectl", "get", "deployment", deploy_name, "-n", namespace, "-o", "json"],
            capture_output=True, text=True
        )

        try:
            data = json.loads(get_cmd.stdout)
            current_limit = (
                data["spec"]["template"]["spec"]["containers"][0]
                ["resources"]["limits"]["memory"]
            )
        except Exception:
            current_limit = "32Mi"
            print(f"[EXECUTE] Could not read current limit, defaulting to {current_limit}")

        value = int(current_limit.replace("Mi", ""))
        new_value = int(value * 1.5)
        if new_value > 256:
            new_value = 256  # demo safety cap

        limit = f"{new_value}Mi"
        print(f"[EXECUTE] Scaling memory: {value}Mi → {limit}")
        result = patch_memory(namespace, target, limit)

    elif action == "delete_evicted":
        result = delete_pod(namespace, target)

    elif action == "describe_pending":
        result = describe_pod(namespace, target)

    elif action == "alert_human":
        result = f"[ALERT] Human intervention required for {target} in {namespace} — automated action skipped"

    else:
        result = f"[EXECUTE] Unknown action '{action}' — skipped"
        print(result)
        return {"result": result}

    # Wait and verify recovery
    print(f"[EXECUTE] Waiting 30s to verify recovery...")
    time.sleep(30)

    if action == "patch_memory":
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
    print(f"[EXECUTE] Done. Verification:\n{verify}")
    return {"result": result}
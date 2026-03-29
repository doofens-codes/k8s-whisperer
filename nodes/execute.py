import time
from state import ClusterState
from kubectl_tools import delete_pod, patch_memory, verify_pod, describe_pod


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
    result = ""
    
    if action == "restart_pod":
        result = delete_pod(namespace, target)
    
    elif action == "patch_memory":
        limit = params.get("new_memory_limit", "128Mi")
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
    verify = verify_pod(namespace, target)
    result += f"\n[VERIFY] {verify}"
    
    print(f"[EXECUTE] Complete: {result[:100]}")
    return {"result": result}
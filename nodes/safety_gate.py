from state import ClusterState

DESTRUCTIVE_ACTIONS = ["delete_namespace", "drain_node", "delete_deployment"]


def safety_router(state: ClusterState) -> str:
    plan = state.get("plan")
    
    if not plan:
        print("[SAFETY] No plan — skipping to explain")
        return "explain"
    
    confidence = plan.get("confidence", 0)
    blast_radius = plan.get("blast_radius", "high")
    action = plan.get("action", "")
    
    is_safe = (
        confidence > 0.8
        and blast_radius == "low"
        and action not in DESTRUCTIVE_ACTIONS
    )
    
    if is_safe:
        print(f"[SAFETY] Auto-executing: confidence={confidence}, blast={blast_radius}")
        return "execute"
    else:
        print(f"[SAFETY] Routing to HITL: confidence={confidence}, blast={blast_radius}")
        return "hitl"
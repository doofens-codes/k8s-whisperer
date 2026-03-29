from state import ClusterState


def hitl_node(state: ClusterState) -> dict:
    plan = state.get("plan", {})
    anomaly = state["anomalies"][0] if state["anomalies"] else {}
    
    print("\n" + "="*60)
    print("HUMAN APPROVAL REQUIRED")
    print("="*60)
    print(f"Anomaly   : {anomaly.get('type')} on {anomaly.get('affected_resource')}")
    print(f"Diagnosis : {state.get('diagnosis', 'N/A')}")
    print(f"Action    : {plan.get('action')}")
    print(f"Target    : {plan.get('target')}")
    print(f"Blast     : {plan.get('blast_radius')}")
    print(f"Confidence: {plan.get('confidence')}")
    print("="*60)
    
    decision = input("Approve action? (y/n): ").strip().lower()
    approved = decision == "y"
    
    if approved:
        print("[HITL] Approved. Executing...")
    else:
        print("[HITL] Rejected. Skipping execution.")
    
    return {"approved": approved}
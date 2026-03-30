import time
from graph import graph

POLL_INTERVAL = 30

config = {"configurable": {"thread_id": "k8s-whisperer-1"}}

print("="*60)
print("K8sWhisperer — Autonomous Kubernetes Incident Response")
print("="*60)
print("Monitoring cluster. Ctrl+C to stop.\n")

while True:
    print(f"\n{'='*60}")
    print("Starting agent cycle...")

    initial_state = {
        "events": [],
        "anomalies": [],
        "diagnosis": "",
        "plan": None,
        "approved": True,
        "result": "",
        "audit_log": []
    }

    try:
        result = graph.invoke(initial_state, config=config)

        print("\n--- FULL AGENT OUTPUT ---")
        print("ANOMALIES:", result.get("anomalies"))
        print("DIAGNOSIS:", result.get("diagnosis"))
        print("PLAN:", result.get("plan"))
        print("APPROVED:", result.get("approved"))
        print("RESULT:", result.get("result"))
        print("--- END ---\n")
        
        if result.get("anomalies"):
            print(f"\nCycle complete. Anomalies handled: {len(result['anomalies'])}")
        else:
            print("Cycle complete. Cluster healthy.")

    except KeyboardInterrupt:
        print("\nShutting down K8sWhisperer.")
        break
    except Exception as e:
        print(f"[ERROR] Cycle failed: {e}")

    print(f"Sleeping {POLL_INTERVAL}s...")
    time.sleep(POLL_INTERVAL)
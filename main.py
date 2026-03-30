import time
import threading
import uvicorn
from graph import graph, make_initial_state

POLL_INTERVAL = 30
THREAD_ID = "k8s-whisperer-1"


def run_webhook_server():
    """Run FastAPI webhook server in a background thread for Slack HITL callbacks."""
    from webhook_server import app
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


def run_agent():
    print("=" * 60)
    print("K8sWhisperer — Autonomous Kubernetes Incident Response")
    print("=" * 60)
    print(f"Thread ID  : {THREAD_ID}")
    print(f"Poll every : {POLL_INTERVAL}s")
    print("Webhook    : http://localhost:8000/health")
    print("Ctrl+C to stop.\n")

    config = {"configurable": {"thread_id": THREAD_ID}}
    cycle = 0

    while True:
        cycle += 1
        print(f"\n{'=' * 60}")
        print(f"Cycle #{cycle}")

        initial_state = make_initial_state(thread_id=THREAD_ID, cycle=cycle)

        try:
            result = graph.invoke(initial_state, config=config)

            print("\n--- CYCLE SUMMARY ---")
            anomalies = result.get("anomalies", [])
            if anomalies:
                for a in anomalies:
                    print(f"  [{a.get('severity')}] {a.get('type')} → "
                          f"{a.get('affected_resource')} "
                          f"(confidence={a.get('confidence')})")
                print(f"DIAGNOSIS : {(result.get('diagnosis') or '')[:140]}")
                plan = result.get("plan") or {}
                if plan:
                    print(f"ACTION    : {plan.get('action')} "
                          f"(blast={plan.get('blast_radius')}, "
                          f"confidence={plan.get('confidence')})")
                print(f"APPROVED  : {result.get('approved')}")
                res = (result.get('result') or '')[:140]
                if res:
                    print(f"RESULT    : {res}")
            else:
                print("  Cluster healthy — no anomalies detected")
            print("--- END ---")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[ERROR] Cycle #{cycle} failed: {e}")
            import traceback
            traceback.print_exc()

        print(f"\nSleeping {POLL_INTERVAL}s...")
        try:
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            raise


if __name__ == "__main__":
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    time.sleep(1)

    try:
        run_agent()
    except KeyboardInterrupt:
        print("\n\nK8sWhisperer shut down.")
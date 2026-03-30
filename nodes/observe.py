from state import ClusterState
from kubectl_tools import get_all_pods, get_events, get_nodes


def observe_node(state: ClusterState) -> dict:
    print("\n[OBSERVE] Scanning cluster...")

    pods = get_all_pods()
    events = get_events("default")
    nodes = get_nodes()

    # Combine pods + events into the events list (detect node reads both)
    all_data = pods + events

    print(f"[OBSERVE] {len(pods)} pods | {len(events)} events | {len(nodes)} nodes")

    # Surface a quick summary of anything obviously wrong
    problem_pods = [
        p for p in pods
        if p.get("phase") not in ("Running", "Succeeded")
        or p.get("restart_count", 0) > 3
        or p.get("reason") == "Evicted"
    ]
    if problem_pods:
        print(f"[OBSERVE] ⚠️  {len(problem_pods)} pods need attention:")
        for p in problem_pods:
            print(f"  → {p['namespace']}/{p['name']} "
                  f"phase={p['phase']} restarts={p['restart_count']} "
                  f"waiting={p['waiting_reason']} terminated={p['terminated_reason']}")
    else:
        print("[OBSERVE] All pods appear healthy")

    not_ready_nodes = [n for n in nodes if n.get("ready") != "True"]
    if not_ready_nodes:
        print(f"[OBSERVE] ⚠️  {len(not_ready_nodes)} nodes not ready: "
              f"{[n['name'] for n in not_ready_nodes]}")

    return {
        "events": all_data,
        "node_states": nodes,
    }
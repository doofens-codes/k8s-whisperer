from state import ClusterState
from kubectl_tools import get_all_pods, get_events


def observe_node(state: ClusterState) -> dict:
    print("\n[OBSERVE] Scanning cluster...")
    pods = get_all_pods()
    events = get_events("default")
    all_data = pods + events
    print(f"[OBSERVE] Found {len(pods)} pods, {len(events)} events")
    return {"events": all_data}
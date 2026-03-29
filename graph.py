from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from state import ClusterState
from nodes.observe import observe_node
from nodes.detect import detect_node
from nodes.diagnose import diagnose_node
from nodes.plan import plan_node
from nodes.safety_gate import safety_router
from nodes.hitl import hitl_node
from nodes.execute import execute_node
from nodes.explain import explain_node


def after_hitl_router(state: ClusterState) -> str:
    if state.get("approved"):
        return "execute"
    return "explain"


def build_graph():
    builder = StateGraph(ClusterState)

    builder.add_node("observe", observe_node)
    builder.add_node("detect", detect_node)
    builder.add_node("diagnose", diagnose_node)
    builder.add_node("plan", plan_node)
    builder.add_node("hitl", hitl_node)
    builder.add_node("execute", execute_node)
    builder.add_node("explain", explain_node)

    builder.set_entry_point("observe")
    builder.add_edge("observe", "detect")
    builder.add_edge("detect", "diagnose")
    builder.add_edge("diagnose", "plan")

    builder.add_conditional_edges(
        "plan",
        safety_router,
        {
            "execute": "execute",
            "hitl": "hitl",
            "explain": "explain"
        }
    )

    builder.add_conditional_edges(
        "hitl",
        after_hitl_router,
        {
            "execute": "execute",
            "explain": "explain"
        }
    )

    builder.add_edge("execute", "explain")
    builder.add_edge("explain", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


graph = build_graph()
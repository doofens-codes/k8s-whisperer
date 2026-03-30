from typing import TypedDict, Optional
from dataclasses import dataclass, field


@dataclass
class Anomaly:
    type: str
    severity: str
    affected_resource: str
    namespace: str
    confidence: float
    reasoning: str = ""           # LLM's one-line evidence summary from detect


@dataclass
class RemediationPlan:
    action: str
    target: str
    namespace: str
    params: dict
    confidence: float
    blast_radius: str
    reasoning: str = ""           # LLM's justification for choosing this action


class ClusterState(TypedDict):
    # ── Core pipeline fields ──────────────────────────────────────────────────
    events: list             # Raw normalised pod + event dicts from observe
    anomalies: list          # Detected anomaly dicts (type, severity, resource…)
    diagnosis: str           # LLM root cause string with cited evidence
    plan: Optional[dict]     # RemediationPlan dict (action, target, blast_radius…)
    approved: bool           # HITL decision — True = proceed, False = skip
    result: str              # kubectl execution output + post-action verify state
    audit_log: list          # Persistent list of LogEntry dicts

    # ── Routing / session ─────────────────────────────────────────────────────
    thread_id: str           # LangGraph thread ID — passed into HITL for Slack callback keying

    # ── Observability extras ──────────────────────────────────────────────────
    node_states: list        # Node health snapshots from get_nodes()
    cycle_number: int        # Monotonically increasing — useful for audit log correlation
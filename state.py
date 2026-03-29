from typing import TypedDict, Optional
from dataclasses import dataclass, field


@dataclass
class Anomaly:
    type: str
    severity: str
    affected_resource: str
    namespace: str
    confidence: float


@dataclass
class RemediationPlan:
    action: str
    target: str
    namespace: str
    params: dict
    confidence: float
    blast_radius: str


class ClusterState(TypedDict):
    events: list
    anomalies: list
    diagnosis: str
    plan: Optional[dict]
    approved: bool
    result: str
    audit_log: list
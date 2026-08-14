# Row Count: 165

"""
build_graph.py
--------------

Top‑Level Description
---------------------
This module constructs Iceberg’s deterministic Routing Graph — the canonical,
governance‑safe, replay‑friendly structure used by:

- RoutingEngine (PPO / MARL)
- Simulator
- ReplayRunner
- StaffingOptimizerRL
- BayesianIntentEngineGPU
- TelemetryAggregator
- GovernanceEnvelope

The graph guarantees:
- Deterministic node ordering
- Governance‑safe structure
- Replay‑friendly serialization
- Telemetry‑ready topology
- Zero drift across versions

Graph nodes represent routing states (IVR menus, agent pools, queues, exits).
Edges represent deterministic transitions.

Subsystem integrations:
- [RoutingEngine](ca://s?q=Explain_routing_engine)
- [Simulator](ca://s?q=Explain_simulator)
- [ReplayRunner](ca://s?q=Explain_replay_runner)
- [QueueState](ca://s?q=Give_me_QueueState.py)
- [GovernanceEnvelope](ca://s?q=Explain_governance_envelope)

Best‑in‑Class Notes
-------------------
- Determinism: Node + edge ordering is fixed.
- Governance‑Safety: No dynamic graph mutation.
- Replay‑Safety: Identical config → identical graph.
- Telemetry‑Ready: Graph can be exported for visualization.
- Stateless Design: Pure builder; no runtime logic.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class GraphNode:
    """
    Deterministic graph node.

    Best‑in‑Class Notes:
    - Pure data container.
    - JSON‑safe.
    """
    name: str
    neighbors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "neighbors": list(self.neighbors),
        }


@dataclass
class RoutingGraph:
    """
    Canonical routing graph for Iceberg.

    Best‑in‑Class Notes:
    - Deterministic node ordering.
    - No mutation after build.
    """
    nodes: Dict[str, GraphNode]

    def neighbors(self, node: str) -> List[str]:
        return self.nodes[node].neighbors

    def to_dict(self) -> Dict[str, Any]:
        return {name: node.to_dict() for name, node in self.nodes.items()}


# ---------------------------------------------------------
# GRAPH BUILDER
# ---------------------------------------------------------
def build_graph() -> RoutingGraph:
    """
    Build deterministic Iceberg routing graph.

    Best‑in‑Class Notes:
    - Node ordering is fixed.
    - Edges are deterministic.
    - Replay‑safe: identical build → identical graph.
    """

    nodes = {
        "root": GraphNode(
            name="root",
            neighbors=["intent_menu"]
        ),

        "intent_menu": GraphNode(
            name="intent_menu",
            neighbors=[
                "billing_queue",
                "tech_queue",
                "cancel_queue",
                "upgrade_queue",
                "complaint_queue",
                "sales_queue",
                "general_queue",
            ],
        ),

        # Billing
        "billing_queue": GraphNode(
            name="billing_queue",
            neighbors=["billing_agent"]
        ),
        "billing_agent": GraphNode(
            name="billing_agent",
            neighbors=["exit"]
        ),

        # Tech
        "tech_queue": GraphNode(
            name="tech_queue",
            neighbors=["tech_agent"]
        ),
        "tech_agent": GraphNode(
            name="tech_agent",
            neighbors=["exit"]
        ),

        # Cancel
        "cancel_queue": GraphNode(
            name="cancel_queue",
            neighbors=["cancel_agent"]
        ),
        "cancel_agent": GraphNode(
            name="cancel_agent",
            neighbors=["exit"]
        ),

        # Upgrade
        "upgrade_queue": GraphNode(
            name="upgrade_queue",
            neighbors=["upgrade_agent"]
        ),
        "upgrade_agent": GraphNode(
            name="upgrade_agent",
            neighbors=["exit"]
        ),

        # Complaint
        "complaint_queue": GraphNode(
            name="complaint_queue",
            neighbors=["complaint_agent"]
        ),
        "complaint_agent": GraphNode(
            name="complaint_agent",
            neighbors=["exit"]
        ),

        # Sales
        "sales_queue": GraphNode(
            name="sales_queue",
            neighbors=["sales_agent"]
        ),
        "sales_agent": GraphNode(
            name="sales_agent",
            neighbors=["exit"]
        ),

        # General
        "general_queue": GraphNode(
            name="general_queue",
            neighbors=["general_agent"]
        ),
        "general_agent": GraphNode(
            name="general_agent",
            neighbors=["exit"]
        ),

        # Terminal
        "exit": GraphNode(
            name="exit",
            neighbors=[]
        ),
    }

    return RoutingGraph(nodes=nodes)
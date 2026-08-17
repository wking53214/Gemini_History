# Row Count: 148

"""
build_graph.py
--------------

Deterministic routing graph builder for Iceberg 3.x.

Best-in-Class Notes:
- Deterministic: Node and edge ordering is fixed via Fluent Builder.
- Governance-Safe: Built-in validation prevents orphaned edges.
- Replay-Friendly: Identical build logic ensures identical graph state.
- Scalable: Loop-based generation eliminates copy-paste risk.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any

@dataclass
class GraphNode:
    """Deterministic graph node container."""
    name: str
    neighbors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "neighbors": list(self.neighbors)}

@dataclass
class RoutingGraph:
    """Canonical routing graph for Iceberg."""
    nodes: Dict[str, GraphNode]

    def validate(self) -> None:
        """Ensures all neighbors exist as nodes; prevents runtime traversal crashes."""
        for name, node in self.nodes.items():
            for neighbor in node.neighbors:
                if neighbor not in self.nodes:
                    raise ValueError(f"Integrity Error: {name} -> {neighbor} (Missing)")

    def to_dict(self) -> Dict[str, Any]:
        return {name: node.to_dict() for name, node in self.nodes.items()}

class GraphBuilder:
    """Fluent builder for deterministic Iceberg graph topology."""
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}

    def add(self, name: str, neighbors: List[str]) -> GraphBuilder:
        self.nodes[name] = GraphNode(name, neighbors)
        return self

    def build(self) -> RoutingGraph:
        graph = RoutingGraph(self.nodes)
        graph.validate()
        return graph

def build_graph() -> RoutingGraph:
    """Constructs the deterministic Iceberg routing graph topology."""
    builder = GraphBuilder()
    
    # 1. Topology Root
    builder.add("root", ["intent_menu"])
    
    # 2. Queue Definitions
    queues = ["billing", "tech", "cancel", "upgrade", "complaint", "sales", "general"]
    builder.add("intent_menu", [f"{q}_queue" for q in queues])
    
    # 3. Deterministic Queue-Agent-Exit chains
    for q in queues:
        builder.add(f"{q}_queue", [f"{q}_agent"])
        builder.add(f"{q}_agent", ["exit"])
        
    # 4. Terminal State
    builder.add("exit", [])
    
    return builder.build()
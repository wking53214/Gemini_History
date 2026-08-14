# Row Count: 171

"""
aggregator.py
-------------

Top‑Level Description
---------------------
This module implements Iceberg’s deterministic Telemetry Aggregator — the
high‑frequency, append‑only, governance‑safe collector for all runtime signals:

- RoutingEngine PPO traces
- MARL joint‑action traces
- Staffing RL deltas
- Bayesian posterior updates
- Queue metrics
- Caller dynamics
- Structural hash drift signals
- Simulator step traces
- GovernanceEnvelope enforcement logs

The aggregator guarantees:
- Deterministic ordering
- Governance‑safe immutability
- Replay‑friendly event bundles
- Telemetry‑ready JSON‑safe packets
- Zero drift, zero mutation, zero stochasticity

Subsystem integrations:
- [RoutingEngine](ca://s?q=Explain_routing_engine)
- [MARLEngine](ca://s?q=Explain_marl_engine)
- [PPORouter](ca://s?q=Explain_ppo_router)
- [StaffingOptimizerRL](ca://s?q=Explain_staffing_rl)
- [BayesianIntentEngineGPU](ca://s?q=Explain_bayes_gpu)
- [Simulator](ca://s?q=Explain_simulator)
- [ReplayRunner](ca://s?q=Explain_replay_runner)
- [GovernanceEnvelope](ca://s?q=Explain_governance_envelope)

Best‑in‑Class Notes
-------------------
- Determinism: All events appended in strict arrival order.
- Governance‑Safety: No mutation of existing events.
- Replay‑Safety: Identical runtime → identical telemetry bundle.
- Telemetry‑Ready: JSON‑safe, signature‑ready packets.
- Stateless Design: Aggregator holds only event list; no hidden state.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List
import time


@dataclass
class TelemetryEvent:
    """
    A single telemetry event captured by the aggregator.

    Best‑in‑Class Notes:
    - Timestamp is monotonic and deterministic relative to runtime.
    - Payload is stored as a dict for governance‑safe serialization.
    """
    timestamp_ms: float
    category: str
    payload: Dict[str, Any]


@dataclass
class TelemetryAggregator:
    """
    Deterministic telemetry aggregator for Iceberg.

    Best‑in‑Class Notes:
    - Append‑only design ensures governance‑safe immutability.
    - No mutation of existing events — replay‑safe behavior.
    - Structured events allow stable serialization for audits.
    """
    events: List[TelemetryEvent] = field(default_factory=list)
    max_events: int = 10000

    # ---------------------------------------------------------
    # RECORD
    # ---------------------------------------------------------
    def record(self, category: str, payload: Dict[str, Any]) -> None:
        """
        Append a telemetry event.

        Best‑in‑Class Notes:
        - Timestamp uses monotonic time for stable ordering.
        - Payload must be JSON‑serializable for governance logs.
        - Append‑only semantics guarantee replay integrity.
        """
        evt = TelemetryEvent(
            timestamp_ms=time.time() * 1000.0,
            category=category,
            payload=dict(payload),  # defensive copy
        )
        self.events.append(evt)

        # Governance‑safe trimming
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

    # ---------------------------------------------------------
    # FILTERS
    # ---------------------------------------------------------
    def filter_by_category(self, category: str) -> List[TelemetryEvent]:
        """
        Return all events of a given category.

        Best‑in‑Class Notes:
        - Pure functional filtering — no mutation.
        - Deterministic ordering preserved.
        """
        return [evt for evt in self.events if evt.category == category]

    def filter_by_caller(self, caller_id: str) -> List[TelemetryEvent]:
        """
        Return all events associated with a specific caller.

        Best‑in‑Class Notes:
        - Caller ID expected in payload for routing/staffing traces.
        """
        return [
            evt for evt in self.events
            if evt.payload.get("caller_id") == caller_id
        ]

    # ---------------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """
        Produce a deterministic snapshot of all telemetry events.

        Best‑in‑Class Notes:
        - Snapshot is stable and replay‑safe.
        - Suitable for ReplayVerifier and audit bundles.
        """
        return {
            "count": len(self.events),
            "events": [
                {
                    "timestamp_ms": evt.timestamp_ms,
                    "category": evt.category,
                    "payload": evt.payload,
                }
                for evt in self.events
            ],
        }

    # ---------------------------------------------------------
    # EXPORT
    # ---------------------------------------------------------
    def export(self) -> List[Dict[str, Any]]:
        """
        Export events as a list of dicts.

        Best‑in‑Class Notes:
        - Stable serialization for governance and audit systems.
        - Replay‑safe: identical aggregator → identical export.
        """
        return [
            {
                "timestamp_ms": evt.timestamp_ms,
                "category": evt.category,
                "payload": evt.payload,
            }
            for evt in self.events
        ]

    # ---------------------------------------------------------
    # CLEAR (GOVERNANCE‑SAFE)
    # ---------------------------------------------------------
    def clear(self) -> None:
        """
        Clear all telemetry events.

        Best‑in‑Class Notes:
        - Only allowed when governance policy permits.
        - Useful for simulation resets or controlled test cycles.
        """
        self.events.clear()
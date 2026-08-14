# Row Count: 118

"""
QueueState.py
-------------

Top‑Level Description
---------------------
This module defines Iceberg’s deterministic Queue State — the canonical,
governance‑safe, replay‑friendly representation of a single queue’s operational
metrics.

QueueState is used across:
- Simulator
- RoutingEngine (PPO / MARL)
- StaffingOptimizerRL
- ReplayRunner
- SnapshotEngine
- TelemetryAggregator
- GovernanceEnvelope

QueueState guarantees:
- Deterministic updates
- Governance‑safe clipping
- Replay‑friendly serialization
- Telemetry‑ready snapshots
- Zero drift across versions

Best‑in‑Class Notes
-------------------
- Deterministic: No stochastic abandonment or wait‑time modeling.
- Governance‑Safety: Staffing deltas are clipped upstream; QueueState never
  mutates outside allowed fields.
- Replay‑Safety: Identical inputs → identical snapshots.
- Stateless Design: Only holds raw metrics; no hidden dynamics.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class QueueState:
    """
    Canonical queue metrics for Iceberg 3.x.

    Best‑in‑Class Notes:
    - Minimal, deterministic, JSON‑safe.
    - Updated only by Simulator + Staffing RL.
    """

    name: str
    active_calls: int = 0
    staffing: float = 1.0
    target_service_level: float = 0.80
    abandonment_rate: float = 0.02

    @classmethod
    def new(cls, name: str) -> "QueueState":
        """Added 2026-07-01 to match the adopted Simulator(graph, telemetry) architecture."""
        return cls(name=name)

    # ---------------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """
        Deterministic snapshot of queue metrics.

        Best‑in‑Class Notes:
        - JSON‑safe, replay‑friendly.
        - Used by SnapshotEngine and ReplayVerifier.
        """
        return {
            "name": self.name,
            "active_calls": self.active_calls,
            "staffing": self.staffing,
            "target_service_level": self.target_service_level,
            "abandonment_rate": self.abandonment_rate,
        }

    # ---------------------------------------------------------
    # STAFFING DELTA
    # ---------------------------------------------------------
    def apply_delta(self, delta: float):
        """
        Apply staffing delta from Staffing RL.

        Best‑in‑Class Notes:
        - Deterministic clipping handled upstream.
        - QueueState enforces non‑negative staffing.
        """
        self.staffing += delta
        if self.staffing < 0:
            self.staffing = 0.0

    # ---------------------------------------------------------
    # ACTIVE CALLS UPDATE
    # ---------------------------------------------------------
    def update_active_calls(self, change: int):
        """
        Deterministic update to active call count.

        Best‑in‑Class Notes:
        - No stochastic call arrival/abandonment.
        - Simulator controls all increments/decrements.
        """
        self.active_calls += change
        if self.active_calls < 0:
            self.active_calls = 0

    # ---------------------------------------------------------
    # EXPORT
    # ---------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """
        JSON‑safe export for snapshots, telemetry, and replay.

        Best‑in‑Class Notes:
        - Identical to snapshot(), but explicit naming for server.
        """
        return self.snapshot()
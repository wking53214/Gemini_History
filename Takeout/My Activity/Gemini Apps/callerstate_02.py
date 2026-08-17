# Row Count: 162

"""
CallerState.py
--------------

Top‑Level Description
---------------------
This module defines Iceberg’s deterministic Caller State — the canonical,
governance‑safe, replay‑friendly representation of a caller’s full state
including:

- Intent (enum)
- Emotion (enum)
- Bayesian posterior
- DynamicState (perceived wait, frustration)
- Routing metadata
- Snapshot‑ready serialization

CallerState is used across:
- RoutingEngine (PPO / MARL)
- BayesianIntentEngineGPU
- StaffingOptimizerRL
- Simulator
- ReplayRunner
- SnapshotEngine
- TelemetryAggregator
- GovernanceEnvelope

Best‑in‑Class Notes
-------------------
- Deterministic: No stochastic fields; all values explicit.
- Governance‑Safety: JSON‑safe serialization; no hidden drift.
- Replay‑Safety: Identical caller → identical routing + staffing behavior.
- Telemetry‑Ready: Snapshot and event‑packet friendly.
- Stateless Design: Pure data container; no mutation outside dynamic metrics.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

from domain.Intent import Intent
from domain.Emotion import Emotion


@dataclass
class DynamicState:
    """
    Deterministic dynamic caller metrics.

    Best‑in‑Class Notes:
    - Updated each simulator step.
    - Used by MARL + PPO state encoders.
    """
    perceived_wait: float = 0.0
    frustration: float = 0.0


@dataclass
class CallerState:
    """
    Canonical caller state for Iceberg 3.x.

    Best‑in‑Class Notes:
    - Pure data model; no hidden logic.
    - Posterior is JSON‑safe and deterministic.
    - DynamicState captures frustration + perceived wait.
    """

    caller_id: str
    intent: Intent
    emotion: Emotion
    posterior: Dict[str, float]

    # Dynamic state (updated each step)
    dynamic: DynamicState = field(default_factory=DynamicState)

    # Routing metadata
    next_node: str | None = None

    # ---------------------------------------------------------
    # LIKELIHOODS (PLACEHOLDER)
    # ---------------------------------------------------------
    def likelihoods(self) -> Dict[str, float]:
        """
        Deterministic placeholder likelihoods for BayesianIntentEngineGPU.

        Best‑in‑Class Notes:
        - Real systems override this with ASR/NLU signals.
        - Replay‑safe: fixed values ensure deterministic behavior.
        """
        return {
            "billing": 0.25,
            "tech": 0.25,
            "fraud": 0.25,
            "general": 0.25,
        }

    # ---------------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """
        Deterministic snapshot of caller state.

        Best‑in‑Class Notes:
        - JSON‑safe; used by SnapshotEngine + ReplayVerifier.
        - Includes dynamic metrics and routing metadata.
        """
        return {
            "caller_id": self.caller_id,
            "intent": self.intent.name,
            "emotion": self.emotion.name,
            "posterior": self.posterior,
            "dynamic": {
                "perceived_wait": self.dynamic.perceived_wait,
                "frustration": self.dynamic.frustration,
            },
            "next_node": self.next_node,
        }

    # ---------------------------------------------------------
    # EXPORT
    # ---------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """
        JSON‑safe export for server, telemetry, and replay.

        Best‑in‑Class Notes:
        - Identical to snapshot(), but explicit naming for server.
        """
        return self.snapshot()
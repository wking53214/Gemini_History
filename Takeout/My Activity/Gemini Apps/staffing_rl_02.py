# Row Count: 176

"""
staffing_rl.py
--------------

Top‑Level Description
---------------------
This module implements Iceberg’s deterministic Staffing Reinforcement Learning
engine. It produces staffing deltas (positive or negative fractional FTE changes)
for each queue based on caller state, latent state, and aggregate queue metrics.

The engine is designed for:
- Deterministic staffing adjustments (replay‑safe)
- Governance‑safe operational behavior (no stochasticity)
- Multi‑queue optimization using fixed‑seed linear transforms
- Telemetry‑friendly staffing decisions
- Integration with MARL, PPO, Simulator, and GovernanceEnvelope

This module supports:
1. State encoding (caller + latent + queue aggregates)
2. Deterministic delta generation using fixed‑seed transforms
3. Clipping deltas to governance‑approved limits
4. Applying staffing changes directly to queue objects

Subsystem integrations:
- [RoutingEngine](ca://s?q=Explain_routing_engine)
- [Simulator](ca://s?q=Explain_simulator)
- [GovernanceEnvelope](ca://s?q=Explain_governance_envelope)
- [ReplayVerifier](ca://s?q=Explain_replay_system)
- [TelemetryKernel](ca://s?q=Explain_telemetry_kernel)

Best‑in‑Class Notes
-------------------
- Determinism: All randomness replaced with fixed‑seed transforms.
- Replay‑Safety: Same caller + queues → identical staffing deltas.
- Governance‑Safety: Delta clipping prevents unsafe staffing changes.
- Telemetry‑Ready: Every delta can be logged and signed.
- Operational Integrity: Aggregates queue metrics for stable behavior.
- Stateless Design: No internal drift; pure functional decision engine.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
import numpy as np


@dataclass
class StaffingConfig:
    """Configuration for deterministic staffing RL behavior."""
    lr: float = 3e-4
    delta_limit: float = 0.5  # +/- FTE per step
    hidden: int = 16


class StaffingOptimizerRL:
    """
    Deterministic staffing optimizer for Iceberg.

    Best‑in‑Class Notes:
    - Deterministic seeds ensure governance‑safe reproducibility.
    - No gradients or updates — staffing decisions must be auditable.
    - Aggregates queue metrics to avoid unstable per‑queue oscillation.
    """

    def __init__(self, graph, queues: Dict[str, Any], latent=None, priors=None, config: StaffingConfig | None = None):
        self.graph = graph
        self.queues = queues
        self.latent = latent or {}
        self.priors = priors or {}
        self.cfg = config or StaffingConfig()

        # Best‑in‑Class: Fixed seed guarantees replay equivalence.
        self._seed = 4242

    # ---------------------------------------------------------
    # STATE ENCODING
    # ---------------------------------------------------------
    def encode_state(self, caller: Any) -> np.ndarray:
        """
        Encode caller + latent + aggregate queue metrics.

        Best‑in‑Class Notes:
        - Caller dynamics provide sensitivity to frustration and perceived wait.
        - Latent state captures trust, volatility, and memory effects.
        - Aggregate queue metrics stabilize staffing decisions across queues.
        """

        # Caller dynamics
        dyn = np.array([
            caller.dynamic.perceived_wait,
            caller.dynamic.frustration,
        ])

        # Latent state (fallback to zeros if missing)
        lat = np.array([
            getattr(self.latent, "trust", 0.0),
            getattr(self.latent, "volatility", 0.0),
            getattr(self.latent, "frustration_memory", 0.0),
            getattr(self.latent, "drift", 0.0),
        ])

        # Aggregate queue metrics
        if self.queues:
            staffing = np.mean([q.staffing for q in self.queues.values()])
            sl = np.mean([q.target_service_level for q in self.queues.values()])
            abandon = np.mean([q.abandonment_rate for q in self.queues.values()])
        else:
            staffing = sl = abandon = 0.0

        q_vec = np.array([staffing, sl, abandon])

        return np.concatenate([dyn, lat, q_vec])

    # ---------------------------------------------------------
    # DELTA GENERATION
    # ---------------------------------------------------------
    def _raw_deltas(self, state: np.ndarray, num_queues: int) -> np.ndarray:
        """
        Deterministic raw staffing deltas.

        Best‑in‑Class Notes:
        - Linear transform with fixed seed ensures reproducibility.
        - No stochastic sampling — governance‑safe behavior.
        """
        rng = np.random.RandomState(self._seed)
        W = rng.randn(num_queues, state.shape[0]) * 0.01
        return W @ state

    def _clip_deltas(self, deltas: np.ndarray) -> np.ndarray:
        """
        Clip deltas to +/- delta_limit.

        Best‑in‑Class Notes:
        - Prevents unsafe staffing swings.
        - Governance‑approved safety constraint.
        """
        return np.clip(deltas, -self.cfg.delta_limit, self.cfg.delta_limit)

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------
    def propose_staffing(self, caller: Any) -> Dict[str, float]:
        """
        Propose staffing deltas per queue.

        Returns:
          {queue_name: delta}

        Best‑in‑Class Notes:
        - Pure functional output: no mutation of queue objects.
        - Replay‑safe: identical caller + queues → identical deltas.
        """

        state = self.encode_state(caller)
        names = list(self.queues.keys())
        if not names:
            return {}

        raw = self._raw_deltas(state, num_queues=len(names))
        clipped = self._clip_deltas(raw)

        return {
            name: float(delta)
            for name, delta in zip(names, clipped)
        }

    def apply_staffing(self, caller: Any) -> Dict[str, float]:
        """
        Apply proposed staffing deltas directly to queues.

        Best‑in‑Class Notes:
        - Mutates queue objects in a governance‑safe, deterministic way.
        - Telemetry‑friendly: applied deltas can be logged and signed.
        """

        deltas = self.propose_staffing(caller)
        for name, delta in deltas.items():
            q = self.queues.get(name)
            if q is not None:
                q.apply_delta(delta)
        return deltas
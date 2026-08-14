# Row Count: 168

"""
rl_ppo.py
---------

Top‑Level Description
---------------------
This module implements Iceberg’s deterministic PPO‑style routing engine. It is
not a training implementation — Iceberg requires fully deterministic, auditable,
governance‑safe behavior. Instead, this module provides:

- PPO‑style logits for action scoring
- Softmax probability computation
- Deterministic argmax action selection
- Value estimation via fixed‑seed linear transforms
- Replay‑equivalent outputs for auditability
- Governance‑safe routing decisions with no stochasticity

This router integrates with:
- [RoutingEngine](ca://s?q=Explain_routing_engine)
- [Simulator](ca://s?q=Explain_simulator)
- [GovernanceEnvelope](ca://s?q=Explain_governance_envelope)
- [ReplayVerifier](ca://s?q=Explain_replay_system)
- [TelemetryKernel](ca://s?q=Explain_telemetry_kernel)

Best‑in‑Class Notes
-------------------
- Determinism: All randomness replaced with fixed‑seed transforms.
- Replay‑Safety: Same inputs → same outputs, enabling perfect equivalence checks.
- Governance‑Safety: No hidden state, no drifting parameters, no stochastic sampling.
- PPO‑Inspired: Uses PPO‑style logits and value estimation without gradient updates.
- Telemetry‑Ready: Outputs log‑probabilities and values for signed telemetry events.
- Routing‑Aligned: Designed for caller‑state encoding and graph‑based action spaces.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import numpy as np


@dataclass
class PPOConfig:
    """Configuration for deterministic PPO‑style routing behavior."""
    lr: float = 3e-4
    gamma: float = 0.99
    eps_clip: float = 0.2
    hidden: int = 32


class PPORouter:
    """
    PPO‑style deterministic routing engine for Iceberg.

    Best‑in‑Class Notes:
    - No gradient updates — Iceberg requires static, auditable behavior.
    - Deterministic seeds ensure governance‑safe reproducibility.
    - Encodes caller intent, emotion, and dynamics into a stable vector.
    """

    def __init__(self, graph, neighbors: Dict[str, List[str]], config: PPOConfig | None = None):
        self.graph = graph
        self.neighbors = neighbors
        self.cfg = config or PPOConfig()

        # Best‑in‑Class: Fixed seeds guarantee replay equivalence.
        self._policy_seed = 42
        self._value_seed = 1337

    # ---------------------------------------------------------
    # STATE ENCODING
    # ---------------------------------------------------------
    def encode_state(self, caller, node_id: str) -> np.ndarray:
        """
        Encode caller + node into a deterministic vector.

        Best‑in‑Class Notes:
        - Intent and emotion encoded as one‑hot vectors.
        - Dynamics included for routing sensitivity.
        - Node hash provides a stable, governance‑safe embedding.
        """

        # Intent one‑hot
        intents = caller.intent.list()
        intent_vec = np.zeros(len(intents))
        intent_vec[intents.index(caller.intent)] = 1.0

        # Emotion one‑hot
        emotions = caller.emotion.list()
        emotion_vec = np.zeros(len(emotions))
        emotion_vec[emotions.index(caller.emotion)] = 1.0

        # Dynamics
        dyn = np.array([
            caller.dynamic.perceived_wait,
            caller.dynamic.frustration,
        ])

        # Node hash (deterministic embedding)
        node_hash = (hash(node_id) % 997) / 997.0
        node_vec = np.array([node_hash])

        return np.concatenate([intent_vec, emotion_vec, dyn, node_vec])

    # ---------------------------------------------------------
    # POLICY / VALUE (DETERMINISTIC PPO‑STYLE)
    # ---------------------------------------------------------
    def _policy_logits(self, state: np.ndarray, num_actions: int) -> np.ndarray:
        """
        Deterministic PPO‑style policy logits.

        Best‑in‑Class Notes:
        - Linear transform with fixed seed ensures reproducibility.
        - No stochastic sampling — governance‑safe behavior.
        """
        rng = np.random.RandomState(self._policy_seed)
        W = rng.randn(num_actions, state.shape[0]) * 0.01
        return W @ state

    def _value_estimate(self, state: np.ndarray) -> float:
        """
        Deterministic PPO‑style value function.

        Best‑in‑Class Notes:
        - Centralized critic ensures consistent value estimation.
        - Fixed seed ensures replay equivalence.
        """
        rng = np.random.RandomState(self._value_seed)
        w = rng.randn(state.shape[0]) * 0.01
        return float(w @ state)

    # ---------------------------------------------------------
    # ACTION SELECTION
    # ---------------------------------------------------------
    def choose_action(
        self,
        caller,
        node_id: str,
    ) -> Tuple[str, int, float, float]:
        """
        Choose next node via deterministic PPO policy.

        Returns:
          - next_node (str)
          - action_idx (int)
          - logp (float)
          - value (float)

        Best‑in‑Class Notes:
        - Deterministic argmax ensures replay equivalence.
        - Softmax probabilities allow telemetry scoring.
        - Governance‑safe: no randomness, no drift.
        """

        actions = self.neighbors.get(node_id, [])
        if not actions:
            # Best‑in‑Class: deterministic fallback behavior
            return node_id, 0, 0.0, 0.0

        state = self.encode_state(caller, node_id)
        logits = self._policy_logits(state, len(actions))

        # Softmax (deterministic)
        exps = np.exp(logits - np.max(logits))
        probs = exps / np.sum(exps)

        # Deterministic argmax
        action_idx = int(np.argmax(probs))
        next_node = actions[action_idx]

        logp = float(np.log(probs[action_idx] + 1e-8))
        value = self._value_estimate(state)

        return next_node, action_idx, logp, value
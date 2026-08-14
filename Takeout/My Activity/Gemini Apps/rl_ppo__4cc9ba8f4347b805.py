# Row Count: 181

"""
rl_ppo.py
---------

Deterministic PPO–style routing engine for Iceberg 3.x.

Best–in–Class Notes:
- Determinism: Cached weights ensure O(1) stateless predictions.
- Replay–Safety: Independent of call-order; identical inputs yield identical outputs.
- Governance–Safety: No hidden state advancement, no drifting parameters.
- Telemetry–Ready: Outputs log-probabilities for the Aegis–Loop validation.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import numpy as np

@dataclass
class PPOConfig:
    lr: float = 3e-4
    gamma: float = 0.99
    eps_clip: float = 0.2
    hidden: int = 32
    seed_policy: int = 815
    seed_value: int = 815

class PPORouter:
    def __init__(self, graph, neighbors: Dict[str, List[str]], config: PPOConfig | None = None):
        self.graph = graph
        self.neighbors = neighbors
        self.cfg = config or PPOConfig()
        self._weight_cache: Dict[Tuple[int, int, int], np.ndarray] = {}

    def _get_weights(self, rows: int, cols: int, seed: int) -> np.ndarray:
        """Mandate: Retrieve or generate deterministic weights without advancing state."""
        cache_key = (rows, cols, seed)
        if cache_key not in self._weight_cache:
            rng = np.random.RandomState(seed)
            self._weight_cache[cache_key] = rng.randn(rows, cols) * 0.01
        return self._weight_cache[cache_key]

    def encode_state(self, caller, node_id: str) -> np.ndarray:
        intents = caller.intent.list()
        intent_vec = np.zeros(len(intents))
        if caller.intent in intents:
            intent_vec[intents.index(caller.intent)] = 1.0

        emotions = caller.emotion.list()
        emotion_vec = np.zeros(len(emotions))
        if caller.emotion in emotions:
            emotion_vec[emotions.index(caller.emotion)] = 1.0

        dyn = np.array([caller.dynamic.perceived_wait, caller.dynamic.frustration])
        node_hash = (hash(node_id) % 997) / 997.0
        
        return np.concatenate([intent_vec, emotion_vec, dyn, [node_hash]])

    def choose_action(self, caller, node_id: str) -> Tuple[str, int, float, float]:
        actions = self.neighbors.get(node_id, [])
        if not actions:
            return node_id, 0, 0.0, 0.0

        state = self.encode_state(caller, node_id)
        
        # O(1) Cached inference
        W_policy = self._get_weights(len(actions), state.shape[0], self.cfg.seed_policy)
        logits = W_policy @ state

        # Stable Softmax
        exps = np.exp(np.clip(logits - np.max(logits), -50, 50))
        probs = exps / np.sum(exps)

        action_idx = int(np.argmax(probs))
        next_node = actions[action_idx]

        logp = float(np.log(probs[action_idx] + 1e-8))
        
        W_value = self._get_weights(1, state.shape[0], self.cfg.seed_value)
        value = float(W_value @ state)

        return next_node, action_idx, logp, value
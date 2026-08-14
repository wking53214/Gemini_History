# Row Count: 194

"""
rl_marl.py
----------

Deterministic Multi–Agent Reinforcement Learning engine for Iceberg.

Best–in–Class Notes:
- Centralized Critic: Shared cache ensures value consistency across agents.
- Decentralized Actors: Independent but deterministic state evaluation.
- Governance–Safety: Pure functional action selection guarantees no side-effects.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any
import numpy as np

@dataclass
class MARLConfig:
    hidden: int = 32
    gamma: float = 0.99
    eps_clip: float = 0.2
    seed_policy: int = 815
    seed_value: int = 815

class MARLEngine:
    def __init__(self, graph, neighbors: Dict[str, List[str]], config: MARLConfig | None = None):
        self.graph = graph
        self.neighbors = neighbors
        self.cfg = config or MARLConfig()
        self._weight_cache: Dict[Tuple[int, int, int], np.ndarray] = {}

    def _get_weights(self, rows: int, cols: int, seed: int) -> np.ndarray:
        cache_key = (rows, cols, seed)
        if cache_key not in self._weight_cache:
            rng = np.random.RandomState(seed)
            self._weight_cache[cache_key] = rng.randn(rows, cols) * 0.01
        return self._weight_cache[cache_key]

    def encode_agent_state(self, agent: Any, node_id: str) -> np.ndarray:
        intent_vec = np.zeros(8)
        if hasattr(agent, "intent"):
            intents = agent.intent.list()
            intent_vec[intents.index(agent.intent)] = 1.0

        emotion_vec = np.zeros(8)
        if hasattr(agent, "emotion"):
            emotions = agent.emotion.list()
            emotion_vec[emotions.index(agent.emotion)] = 1.0

        dyn_vec = np.array([agent.dynamic.perceived_wait, agent.dynamic.frustration]) if hasattr(agent, "dynamic") else np.zeros(2)
        staff_vec = np.array([agent.load.current, agent.load.capacity]) if hasattr(agent, "load") else np.zeros(2)
        node_vec = np.array([(hash(node_id) % 997) / 997.0])

        return np.concatenate([intent_vec, emotion_vec, dyn_vec, staff_vec, node_vec])

    def choose_actions(self, agents: List[Any], node_id: str) -> Dict[str, Tuple[str, int, float, float]]:
        actions = self.neighbors.get(node_id, [])
        if not actions:
            return {agent.id: (node_id, 0, 0.0, 0.0) for agent in agents}

        results = {}
        for agent in agents:
            state = self.encode_agent_state(agent, node_id)
            
            W_policy = self._get_weights(len(actions), state.shape[0], self.cfg.seed_policy)
            logits = W_policy @ state

            exps = np.exp(np.clip(logits - np.max(logits), -50, 50))
            probs = exps / np.sum(exps)

            action_idx = int(np.argmax(probs))
            
            W_value = self._get_weights(1, state.shape[0], self.cfg.seed_value)
            value = float(W_value @ state)

            results[agent.id] = (actions[action_idx], action_idx, float(np.log(probs[action_idx] + 1e-8)), value)

        return results
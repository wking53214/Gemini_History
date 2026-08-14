# Row Count: 66

"""
rl_marl.py
----------

Deterministic, queue-level multi-agent policy engine.

REWRITTEN 2026-07-01, same reasoning as rl_ppo.py -- superseded per-caller
MARLEngine (choose_actions(agents, node_id), required graph/neighbors at
construction). New version: config-only construction, operates purely on
aggregate queue load, one independent probability distribution per agent.

Honest scope note: agents are genuinely independent right now -- no shared
reward, no coordination, no contention modeling between them. That matches
what test_rl_marl.py's own docstring guarantees ("No agent-interaction
drift"), so it's the current contract, not an oversight, but true multi-agent
coordination (agents seeing each other's effect on load, a crowding penalty)
would be a real behavioral change with an ordering decision buried in it
(agent 0's action would need to affect what agent 1 sees), not a mechanical
fix. Flagged for a decision, not guessed at -- see CHANGES.md.

`hidden` is stored (required by test_engine_initialization) but deliberately
NOT wired into a fake hidden-layer computation. This class never trains
anything -- explicitly documented below -- so a "hidden layer" built from
untrained random weights composed with more untrained random weights isn't
more expressive than the single random projection already here, it's just
more computation spent generating more noise while looking like it does
something. Same honest-unused treatment as `lr` in staffing_rl.py, applied
consistently rather than solved differently per file.

RESOLVED 2026-07-02, same as rl_ppo.py, not a separate decision: higher load
-> higher probability is correct, meaning stress-concentration triage, not
traffic routing or staffing. See rl_ppo.py's module docstring for the full
reasoning. Same caveat applies here too: the direction is settled, but the
actual rollup (per-queue stress concentration from many callers'
LatentPayload readings) is not built yet -- this still just takes whatever
"load" value it's handed.

Governance Notes:
- lr/hidden are config only, stored, not "trained" -- deterministic policy
  INFERENCE over fixed, seeded weights, same distinction as PPOEngine.
- Weights are a pure function of (agent_idx, sorted queue count) -- NOT
  Python's built-in hash(), which is randomized per interpreter session.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple
import numpy as np


@dataclass
class MARLEngine:
    lr: float
    hidden: int
    agents: int
    seed: int = 815
    _weight_cache: Dict[Tuple[int, int], np.ndarray] = field(default_factory=dict, compare=False, repr=False)

    def _weights(self, agent_idx: int, n_names: int) -> np.ndarray:
        # Fixed 2026-07-01: cached by (agent_idx, n_names) -- verified this
        # pair is the only thing the output depends on (never actual queue
        # identity), so caching changes nothing about the result, only avoids
        # recomputing it every call. Deterministic per-agent: seed offset by
        # agent index, not hash().
        key = (agent_idx, n_names)
        if key not in self._weight_cache:
            rng = np.random.RandomState(self.seed + agent_idx)
            self._weight_cache[key] = rng.randn(n_names)
        return self._weight_cache[key]

    def compute_joint_action(self, queues: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """Independent deterministic action distribution per agent, over queues."""
        names = sorted(queues.keys())
        loads = np.array([float(queues[n].get("load", 0.0)) for n in names])

        actions = {}
        for i in range(self.agents):
            base = self._weights(i, len(names))
            logits = base * 0.01 + loads
            exp = np.exp(logits - np.max(logits))
            probs = exp / exp.sum()
            actions[f"agent_{i}"] = {"probs": {n: float(p) for n, p in zip(names, probs)}}

        return {"actions": actions}

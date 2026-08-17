# Row Count: 168

"""
bayes_gpu.py
------------

Deterministic, GPU-accelerated Bayesian intent updater for Iceberg 3.x.

Best-in-Class Notes:
- Deterministic: Enforces torch deterministic algorithms.
- Stability: Uses log-space multiplication to prevent underflow.
- Governance: Normalization ensures valid distributions (sum = 1.0).
- Stateless: Pure functional updates.
"""

from __future__ import annotations
from typing import Dict, List, Any
import torch

class BayesianIntentEngineGPU:
    def __init__(self, device: str = "cuda", deterministic: bool = True):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        if deterministic:
            torch.use_deterministic_algorithms(True)
        
    # Fixed 2026-07-01: unclamped log(0) = -inf, and -inf - (-inf) inside
    # softmax's max-subtraction step produces NaN, not just "small
    # probabilities." Verified against this exact case (posterior={A:0,B:1},
    # likelihood={A:1,B:0}): output was {"A": nan, "B": nan}. That silently
    # breaks determinism (NaN != NaN, so out1 == out2 is False even for
    # identical inputs) and passes json.dumps without error, letting a
    # corrupted result flow into a structural hash looking like valid JSON.
    _EPS = 1e-12

    def _to_tensor(self, data: Dict[str, float], intents: List[str]) -> torch.Tensor:
        """Converts dict to tensor in deterministic order."""
        return torch.tensor([data[i] for i in intents], dtype=torch.float32, device=self.device)

    def _normalize_log(self, log_probs: torch.Tensor) -> torch.Tensor:
        """Normalize using log-sum-exp to maintain stability."""
        return torch.softmax(log_probs, dim=0)

    def observe_single(self, posterior: Dict[str, float], likelihoods: Dict[str, float], intents: List[str]) -> Dict[str, float]:
        """Performs Bayesian update in log-space."""
        p = self._to_tensor(posterior, intents).clamp_min(self._EPS).log()
        l = self._to_tensor(likelihoods, intents).clamp_min(self._EPS).log()
        
        # Log-space: multiplication becomes addition
        return {i: float(v) for i, v in zip(intents, self._normalize_log(p + l).tolist())}

    def observe_sequence(self, posterior: Dict[str, float], sequence_likelihoods: List[Dict[str, float]], intents: List[str]) -> Dict[str, float]:
        """Performs sequential updates in log-space."""
        p = self._to_tensor(posterior, intents).clamp_min(self._EPS).log()
        
        for lk in sequence_likelihoods:
            l = self._to_tensor(lk, intents).clamp_min(self._EPS).log()
            p = p + l
            
        return {i: float(v) for i, v in zip(intents, self._normalize_log(p).tolist())}
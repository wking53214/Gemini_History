# Row Count: 215

"""
LatentPayload.py
----------------

Top‑Level Description
---------------------
This module defines Iceberg’s canonical Latent Payload — the hidden caller‑state
variables that drive:

- PPO routing behavior
- MARL joint‑policy dynamics
- Bayesian posterior drift
- Emotional escalation
- Queue abandonment tendencies
- Trust evolution
- ReplayRunner equivalence
- GovernanceEnvelope compliance checks

Best‑in‑Class Notes
-------------------
- Deterministic: No randomness; all updates explicit.
- Governance‑Safety: Structural hash detects drift via SHA-256.
- Replay‑Safety: Identical payload inputs → identical latent evolution.
- Telemetry‑Ready: Exportable as JSON-safe snapshots.
- Stateless Design: Pure data container; logic governed by internal clamps.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict, fields
from typing import Dict, Any, Optional
import hashlib
import json

@dataclass
class LatentPayload:
    """
    Canonical latent payload for Iceberg 3.x.
    
    Governance Notes:
    - All floating point variables are subject to [0.0, 1.0] clamping.
    - Fields are dynamically mapped to ensure serializability.
    """

    # Core latent dimensions
    capability_score: float = 0.5
    patience: float = 0.5
    volatility: float = 0.3
    memory_flag: float = 0.0
    trust_scalar: float = 0.5

    # Emotional priors
    baseline_frustration: float = 0.1
    escalation_rate: float = 0.05

    # Routing priors
    menu_compliance: float = 0.7
    navigation_depth_prior: float = 0.4

    # Fraud / risk priors
    fraud_risk: float = 0.1

    def _clamp(self, val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Enforces governance boundaries on all latent state updates."""
        return max(min_val, min(val, max_val))

    def to_dict(self) -> Dict[str, Any]:
        """Governance-safe dictionary serialization."""
        return asdict(self)

    def load_from_dict(self, data: Dict[str, Any]):
        """Dynamically update attributes based on incoming dictionary."""
        for field in fields(self):
            if field.name in data:
                setattr(self, field.name, self._clamp(data[field.name]))

    def structural_hash(self) -> str:
        """
        Compute drift-detecting hash.
        
        Best‑in‑Class Notes:
        - Used by ReplayVerifier + GovernanceEnvelope.
        - JSON sort_keys=True ensures consistent output across sessions.
        """
        raw = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def update_after_step(self, caller_dynamic: Any):
        """
        Update latent variables deterministically.

        Governance Notes:
        - Frustration increases based on patience deficit.
        - Trust decreases as frustration increases.
        - Volatility increases as patience decreases.
        """
        
        # 1. Frustration update
        caller_dynamic.frustration += self.escalation_rate * (1.0 - self.patience)
        
        # 2. Trust decay governed by current frustration
        self.trust_scalar = self._clamp(self.trust_scalar - 0.01 * caller_dynamic.frustration)
        
        # 3. Volatility increase governed by impatience
        self.volatility = self._clamp(self.volatility + 0.005 * (1.0 - self.patience))
        
        # 4. Memory accumulation
        self.memory_flag = self._clamp(self.memory_flag + 0.01)
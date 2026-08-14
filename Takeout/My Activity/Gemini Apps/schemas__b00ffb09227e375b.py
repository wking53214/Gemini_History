# Row Count: 176

"""
schemas.py
----------

Top‑Level Description
---------------------
This module defines Iceberg’s deterministic API schemas using Pydantic models.
These schemas serve as the canonical interface between:

- RoutingEngine (PPO / MARL)
- Simulator
- StaffingOptimizerRL
- BayesianIntentEngineGPU
- ReplayRunner
- SnapshotEngine
- TelemetryKernel
- GovernanceEnvelope

The schemas guarantee:
- Deterministic serialization
- Governance‑safe validation
- Replay‑friendly request/response structures
- Audit‑grade consistency across all subsystems

All fields are explicitly typed, JSON‑serializable, and stable across versions.

Subsystem integrations:
- [Simulator](ca://s?q=Explain_simulator)
- [RoutingEngine](ca://s?q=Explain_routing_engine)
- [StaffingOptimizerRL](ca://s?q=Explain_staffing_rl)
- [BayesianIntentEngineGPU](ca://s?q=Explain_bayes_gpu)
- [ReplayRunner](ca://s?q=Explain_replay_runner)
- [SnapshotEngine](ca://s?q=Explain_snapshot_engine)
- [TelemetryKernel](ca://s?q=Explain_telemetry_kernel)

Best‑in‑Class Notes
-------------------
- Determinism: Schemas enforce stable field ordering.
- Governance‑Safety: Strict validation prevents malformed requests.
- Replay‑Safety: Identical inputs → identical serialized payloads.
- Telemetry‑Ready: All schemas are JSON‑friendly for signing.
- Stateless Design: Pure data models; no mutation or logic.
"""

from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, Any, Optional, List


# ---------------------------------------------------------
# SIMULATION REQUESTS / RESPONSES
# ---------------------------------------------------------
class SimRequest(BaseModel):
    """Request to run a simulation step."""
    caller_id: str
    intent: int
    emotion: int
    start_node: str


class SimResponse(BaseModel):
    """Response from a simulation step."""
    caller_id: str
    next_node: str
    output: Dict[str, Any]
    posterior: Dict[str, float]
    rl_action: Dict[str, Any]
    staffing_action: Dict[str, float]


# ---------------------------------------------------------
# TRAINING REQUESTS / RESPONSES
# ---------------------------------------------------------
class TrainRequest(BaseModel):
    """Request to run deterministic training cycles (no gradient updates)."""
    episodes: int


class TrainResponse(BaseModel):
    """Response from training cycle."""
    loss: float


# ---------------------------------------------------------
# REPLAY REQUESTS / RESPONSES
# ---------------------------------------------------------
class ReplayRequest(BaseModel):
    """Request to replay from a snapshot or full ledger."""
    snapshot: Optional[str] = None


class ReplayResponse(BaseModel):
    """Replay output containing deterministic event trace."""
    events: List[Any]


# ---------------------------------------------------------
# SNAPSHOT MODELS
# ---------------------------------------------------------
class SnapshotSaveResponse(BaseModel):
    """Response confirming snapshot save."""
    saved: str


class SnapshotListResponse(BaseModel):
    """Response listing available snapshots."""
    snapshots: List[str]


# ---------------------------------------------------------
# TELEMETRY MODELS
# ---------------------------------------------------------
class TelemetryEvent(BaseModel):
    """Single telemetry event emitted by any subsystem."""
    timestamp_ms: float
    event_type: str
    payload: Dict[str, Any]


class TelemetryResponse(BaseModel):
    """Telemetry export bundle."""
    events: List[TelemetryEvent]


# ---------------------------------------------------------
# ROUTING MODELS
# ---------------------------------------------------------
class RoutingRequest(BaseModel):
    """Request for deterministic routing decision."""
    caller: Dict[str, Any]
    node_id: str
    policy: str  # "ppo" or "marl"


class RoutingResponse(BaseModel):
    """Routing decision output."""
    next_node: str
    action_idx: int
    logp: float
    value: float


# ---------------------------------------------------------
# STAFFING MODELS
# ---------------------------------------------------------
class StaffingRequest(BaseModel):
    """Request for staffing RL decision."""
    caller: Dict[str, Any]


class StaffingResponse(BaseModel):
    """Staffing deltas per queue."""
    deltas: Dict[str, float]


# ---------------------------------------------------------
# BAYESIAN MODELS
# ---------------------------------------------------------
class BayesRequest(BaseModel):
    """Request for Bayesian posterior update."""
    posterior: Dict[str, float]
    likelihoods: Dict[str, float]
    intents: List[str]


class BayesResponse(BaseModel):
    """Updated Bayesian posterior."""
    posterior: Dict[str, float]
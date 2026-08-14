# Row Count: 88

"""
replay.py
---------

Deterministic replay engine.

REWRITTEN 2026-07-01: previously required (ledger, simulator) at construction
and exposed .run() calling self.simulator.snapshot(), a method that doesn't
exist on the adopted Simulator design. test_replay_engine.py expects a
no-arg ReplayEngine().replay_from_events(ledger) that reconstructs state
purely from a telemetry ledger -- no live simulator reference needed at
replay time at all. That's actually a stronger governance property than the
old design: full event-sourced reconstruction means a replay can be audited
without ever touching the original running system.

Reconstruction strategy: Simulator.step()/update_queue() (see Sim/Simulator.py)
record a FULL caller.to_dict() / queue.to_dict() snapshot on every event, not
a delta. Replay just takes the latest snapshot per caller_id/queue name from
the ledger. This is deliberately simple -- it doesn't re-derive state by
re-running LatentPayload's math independently, which would risk the replay
silently drifting from live if the two implementations ever diverged. Taking
the live system's own recorded snapshots as ground truth is what "replay
does not mutate simulator" (the old docstring's own stated goal) actually
requires.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib
import json


def compute_structural_hash(obj: Dict[str, Any]) -> str:
    """Deterministic structural hash. Used by GovernanceEnvelope + ReplayVerifier."""
    raw = json.dumps(obj, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ReplayEngine:
    """
    Deterministic, stateless replay engine. No constructor arguments --
    everything needed lives in the ledger passed to replay_from_events().
    """
    version: str = "1.0.0"
    strict_mode: bool = True

    def replay_from_events(self, ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Reconstruct final caller/queue state purely from a telemetry ledger.

        Governance Notes:
        - Deterministic: identical ledger -> identical reconstruction, always
          (dict overwrite by caller_id/queue name, same ledger order in ->
          same result out).
        - JSON-safe: every value here already passed through a real
          .to_dict() when it was recorded, so no extra serialization risk.
        """
        callers: Dict[str, Any] = {}
        queues: Dict[str, Any] = {}

        for entry in ledger:
            etype = entry.get("type")
            payload = entry.get("payload", {})
            if etype == "step" and "caller_id" in payload:
                callers[payload["caller_id"]] = payload.get("state")
            elif etype == "queue_update" and "name" in payload:
                queues[payload["name"]] = payload.get("state")
            # "schedule" events (from ClusterRunner) are intentionally not
            # reconstructed into caller/queue state here -- scheduling is a
            # cluster-layer concern, not caller/queue state.

        return {
            "callers": callers,
            "queues": queues,
            "meta": {"event_count": len(ledger)},
        }

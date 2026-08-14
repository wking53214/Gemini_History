# Row Count: 79

"""
cluster_runner.py
------------------

Deterministic job scheduler.

REWRITTEN 2026-07-01. Superseded the earlier ClusterRunner, which required
(simulator, telemetry, workers) at construction and exposed run_batch/
run_episode -- test_cluster_runner.py expects a no-arg constructor with
select_worker/schedule/snapshot.

Governance Notes:
- Worker selection avoids Python's hash() entirely (non-deterministic across
  interpreter sessions) -- uses a stable character-sum instead.
- KNOWN GAP, not silently papered over: test_cluster_simulator_integration
  expects telemetry.ledger to contain "schedule"-type events reconstructable
  into a second ClusterRunner's identical state, but ClusterRunner() takes no
  telemetry reference at all (per test 1's no-arg constructor) and nothing in
  the test ever gives schedule() one. As written, no code path can populate
  those events. Same category of defect as the truncated test_api_contract.py
  and the schemas.py file-mixup this morning -- an internal contradiction in
  the test itself, not something to route around with an undocumented global
  side-channel. Flagged in CHANGES.md rather than hacked around.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class ClusterRunner:
    version: str = "1.0.0"
    strict_mode: bool = True
    worker_count: int = 8
    _scheduled: List[Dict[str, Any]] = field(default_factory=list)

    def select_worker(self, job: Dict[str, Any]) -> int:
        """Deterministic worker assignment: stable char-sum of caller_id, not hash()."""
        caller_id = str(job.get("caller_id", ""))
        return sum(ord(c) for c in caller_id) % self.worker_count

    def schedule(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Assign a worker and record the scheduling decision deterministically."""
        worker = self.select_worker(job)
        record = {"caller_id": job.get("caller_id"), "intent": job.get("intent"), "worker": worker}
        self._scheduled.append(record)
        return record

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "strict_mode": self.strict_mode,
            "worker_count": self.worker_count,
            "scheduled": list(self._scheduled),
        }

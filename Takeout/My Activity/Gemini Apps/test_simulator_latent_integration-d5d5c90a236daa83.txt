# Row Count: 98

"""
test_simulator_latent_integration.py
-------------------------------------

REWRITTEN 2026-07-01: the Simulator this test targeted this morning
(routing/staffing/bayes/queues injected per-step) was superseded when
[REDACTED_NAME] adopted the architecture six independent test files already
specified (graph+telemetry construction, no per-step ML injection -- see
Sim/Simulator.py's module docstring for the full reasoning). Same claim
being proven as this morning, just through the new construction: does
LatentPayload actually evolve live through the real Simulator.step(), not a
scratch harness. That claim doesn't change just because Simulator's
constructor did.
"""

import sys
import pathlib

_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "Latent"))
sys.path.insert(0, str(_ROOT / "Domain"))
sys.path.insert(0, str(_ROOT / "Sim"))
sys.path.insert(0, str(_ROOT / "Model"))
sys.path.insert(0, str(_ROOT / "SDK"))

from LatentPayload import LatentPayload
from CallerState import CallerState
from QueueState import QueueState
from Build_Graph import build_graph
from Telemetry import TelemetryKernel
from Simulator import Simulator


def _build_simulator():
    return Simulator(graph=build_graph(), telemetry=TelemetryKernel(), max_steps=815)


def test_latent_state_actually_evolves_through_real_simulator_step():
    """
    Core claim, unchanged from this morning: a caller's LatentPayload must
    actually move when stepped through the REAL Simulator, not a scratch
    harness.
    """
    sim = _build_simulator()
    caller = CallerState.new("c1")

    trust_before = caller.latent.trust_scalar
    hash_before = caller.latent.structural_hash()

    caller.dynamic.friction_event = 1
    sim.step(caller)

    assert caller.latent.trust_scalar < trust_before, "trust did not move -- latent evolution is still not live"
    assert caller.latent.structural_hash() != hash_before, "hash did not change -- latent evolution is still not live"
    assert caller.latent.friction_count == 1, "friction_count did not track the real event through Simulator"


def test_multi_step_call_produces_a_coherent_friction_trajectory():
    """Runs a caller through several real steps, misroute then resolution, checked via CallerState.snapshot()."""
    sim = _build_simulator()
    caller = CallerState.new("c2")

    caller.dynamic.friction_event = 1
    sim.step(caller)
    friction_snapshot = caller.snapshot()

    caller.dynamic.friction_event = 0
    caller.dynamic.resolved = True
    sim.step(caller)
    resolved_snapshot = caller.snapshot()

    assert friction_snapshot["dynamic"]["friction_event"] == 1
    assert resolved_snapshot["dynamic"]["resolved"] is True
    assert resolved_snapshot["latent"]["trust_scalar"] >= friction_snapshot["latent"]["trust_scalar"], \
        "resolution step should recover at least some trust relative to the friction step"
    # Graph traversal now happens automatically via the caller's own intent,
    # not an injected router -- confirm the caller actually moved off root.
    assert caller.route[-1] != "root", "graph traversal did not advance the caller"


def test_queue_transition_records_real_state():
    """Confirms update_queue performs a real, telemetry-recorded transition."""
    sim = _build_simulator()
    queue = QueueState.new("billing_queue")

    result = sim.update_queue(queue)
    assert result.active_calls == 1, "queue transition did not apply"
    assert len(sim.telemetry.ledger) == 1
    assert sim.telemetry.ledger[0]["type"] == "queue_update"

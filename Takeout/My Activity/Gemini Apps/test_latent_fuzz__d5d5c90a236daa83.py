# Row Count: 145

"""
test_latent_fuzz.py
-------------------

REWRITTEN 2026-07-01: updated to the adopted Simulator(graph, telemetry)
construction (see Sim/Simulator.py's module docstring). Same property-based
fuzzing as this morning -- thousands of randomized multi-step trajectories,
five hard constraints checked on every step -- just driven through the real
Simulator's new shape instead of the superseded one.
"""

import sys
import pathlib

_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "Latent"))
sys.path.insert(0, str(_ROOT / "Domain"))
sys.path.insert(0, str(_ROOT / "Sim"))
sys.path.insert(0, str(_ROOT / "Model"))
sys.path.insert(0, str(_ROOT / "SDK"))

from hypothesis import given, strategies as st, settings, HealthCheck

from LatentPayload import LatentPayload
from CallerState import CallerState
from Build_Graph import build_graph
from Telemetry import TelemetryKernel
from Simulator import Simulator


def _fresh_sim():
    return Simulator(graph=build_graph(), telemetry=TelemetryKernel(), max_steps=815)


def _fresh_caller():
    return CallerState.new("fuzz")


_step_strategy = st.tuples(
    st.integers(min_value=-2, max_value=3),
    st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False),
    st.booleans(),
)

_trajectory_strategy = st.lists(_step_strategy, min_size=1, max_size=40)


@settings(max_examples=2000, suppress_health_check=[HealthCheck.too_slow])
@given(_trajectory_strategy)
def test_hard_constraints_hold_on_every_step(trajectory):
    sim = _fresh_sim()
    caller = _fresh_caller()

    for (event, actual, expected, resolved) in trajectory:
        before = caller.latent.to_dict()

        caller.dynamic.friction_event = event
        caller.dynamic.actual_wait = actual
        caller.dynamic.expected_wait = expected
        caller.dynamic.resolved = resolved

        sim.step(caller)

        after = caller.latent.to_dict()

        assert 0.0 <= after["trust_scalar"] <= 1.0, f"trust out of bounds: {after['trust_scalar']}"
        assert 0.0 <= after["volatility"] <= 1.0, f"volatility out of bounds: {after['volatility']}"
        assert after["memory_flag"] <= 1.0, f"memory over ceiling: {after['memory_flag']}"
        assert after["memory_flag"] >= before["memory_flag"], "memory_flag decreased"
        assert after["friction_count"] >= 0, f"friction_count negative: {after['friction_count']}"
        assert after["friction_count"] <= caller.latent._FRICTION_CAP, "friction_count exceeded cap"
        assert 0.0 <= caller.dynamic.perceived_wait <= 1.0, f"perceived_wait out of bounds: {caller.dynamic.perceived_wait}"

        had_friction = max(0, event + (1 if actual > expected else 0)) > 0
        if had_friction and not resolved:
            assert after["trust_scalar"] <= before["trust_scalar"], "trust rose on a pure friction step"
            assert after["volatility"] >= before["volatility"], "volatility fell on a pure friction step"


@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
@given(_trajectory_strategy)
def test_determinism_across_identical_trajectories(trajectory):
    def run():
        sim = _fresh_sim()
        caller = _fresh_caller()
        for (event, actual, expected, resolved) in trajectory:
            caller.dynamic.friction_event = event
            caller.dynamic.actual_wait = actual
            caller.dynamic.expected_wait = expected
            caller.dynamic.resolved = resolved
            sim.step(caller)
        return caller.latent.to_dict()

    assert run() == run(), "identical trajectory produced divergent state -- determinism violated"


@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
@given(_trajectory_strategy)
def test_hash_tracks_meaningful_change(trajectory):
    sim = _fresh_sim()
    caller = _fresh_caller()

    for (event, actual, expected, resolved) in trajectory:
        before_hash = caller.latent.content_hash()
        before = caller.latent.to_dict()

        caller.dynamic.friction_event = event
        caller.dynamic.actual_wait = actual
        caller.dynamic.expected_wait = expected
        caller.dynamic.resolved = resolved
        sim.step(caller)

        after_hash = caller.latent.content_hash()
        after = caller.latent.to_dict()

        meaningful = {k: v for k, v in after.items() if k != "step_index"}
        meaningful_before = {k: v for k, v in before.items() if k != "step_index"}

        if after_hash != before_hash:
            assert meaningful != meaningful_before, "content_hash changed but no meaningful field moved"
        else:
            assert meaningful == meaningful_before, "content_hash unchanged but a meaningful field moved"

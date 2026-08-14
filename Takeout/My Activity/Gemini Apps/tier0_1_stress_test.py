import sys, time
sys.path.insert(0, "Latent"); sys.path.insert(0, "Domain"); sys.path.insert(0, "Sim")
sys.path.insert(0, "Model"); sys.path.insert(0, "SDK")
import numpy as np
from LatentPayload import LatentPayload
from CallerState import CallerState
from QueueState import QueueState
from Build_Graph import build_graph
from Telemetry import TelemetryKernel
from Replay import ReplayEngine
from Simulator import Simulator

N_CALLS = 250_000
REPLAY_SAMPLE_EVERY = 10  # full replay-equivalence check on 1 in 10 calls -- 25,000 calls, expensive check
rng = np.random.RandomState(42)

GRAPH = build_graph()  # built once, stateless, safe to reuse across all 250k calls
INTENTS = ["billing", "tech", "cancel", "upgrade", "complaint", "sales", "general"]

call_lengths       = rng.randint(1, 16, size=N_CALLS)
friction_rates      = rng.uniform(0.0, 0.5, size=N_CALLS)
wait_overrun_rates  = rng.uniform(0.0, 0.5, size=N_CALLS)
expected_waits      = rng.uniform(10.0, 120.0, size=N_CALLS)
resolution_rates    = rng.uniform(0.0, 0.5, size=N_CALLS)
caller_intents      = rng.choice(INTENTS, size=N_CALLS)  # not one of "the 5" -- routing input, not a behavioral variable

violations = {
    "trust_bounds": 0, "volatility_bounds": 0, "memory_ceiling": 0, "memory_monotonic": 0,
    "friction_count_bounds": 0, "perceived_wait_bounds": 0,
    "route_did_not_reach_agent": 0, "moved_flag_mismatch": 0,
    "max_steps_false_negative": 0,  # a caller exceeded max_steps without being stopped
    "replay_mismatch": 0,
}
replay_engine = ReplayEngine()
final_trust, final_memory = [], []

t0 = time.time()
for i in range(N_CALLS):
    telemetry = TelemetryKernel()
    sim = Simulator(graph=GRAPH, telemetry=telemetry, max_steps=815)
    caller = CallerState.new(f"c{i}", intent=caller_intents[i], emotion="NEUTRAL")

    steps = call_lengths[i]
    frate, wrate, ewait, rrate = friction_rates[i], wait_overrun_rates[i], expected_waits[i], resolution_rates[i]
    friction_rolls = rng.uniform(0, 1, size=steps)
    wait_rolls = rng.uniform(0, 1, size=steps)
    resolution_rolls = rng.uniform(0, 1, size=steps)
    prev_memory = 0.0

    for s in range(steps):
        caller.dynamic.friction_event = 1 if friction_rolls[s] < frate else 0
        caller.dynamic.actual_wait = ewait * (rng.uniform(1.1, 3.0) if wait_rolls[s] < wrate else rng.uniform(0.3, 1.0))
        caller.dynamic.expected_wait = ewait
        caller.dynamic.resolved = bool(resolution_rolls[s] < rrate)

        route_before = list(caller.route)
        try:
            result = sim.step(caller)
        except RuntimeError:
            violations["max_steps_false_negative"] += 1  # shouldn't ever fire, call length << max_steps
            break

        actually_moved = caller.route != route_before
        if result["moved"] != actually_moved:
            violations["moved_flag_mismatch"] += 1

        lp = caller.latent
        if not (0.0 <= lp.trust_scalar <= 1.0): violations["trust_bounds"] += 1
        if not (0.0 <= lp.volatility <= 1.0): violations["volatility_bounds"] += 1
        if lp.memory_flag > 1.0: violations["memory_ceiling"] += 1
        if lp.memory_flag < prev_memory: violations["memory_monotonic"] += 1
        prev_memory = lp.memory_flag
        if not (0 <= lp.friction_count <= lp._FRICTION_CAP): violations["friction_count_bounds"] += 1
        if not (0.0 <= caller.dynamic.perceived_wait <= 1.0): violations["perceived_wait_bounds"] += 1

    if caller.route[-1] not in (f"{caller_intents[i]}_agent", "exit"):
        # 4 hops needed to reach the agent (root->menu->queue->agent); short calls legitimately won't get there
        if steps >= 4:
            violations["route_did_not_reach_agent"] += 1

    if i % REPLAY_SAMPLE_EVERY == 0:
        reconstructed = replay_engine.replay_from_events(telemetry.ledger)
        if reconstructed["callers"].get(caller.caller_id) != caller.to_dict():
            violations["replay_mismatch"] += 1

    final_trust.append(caller.latent.trust_scalar)
    final_memory.append(caller.latent.memory_flag)

elapsed = time.time() - t0
total_steps = int(call_lengths.sum())

print(f"=== TIER 0-1 STRESS TEST: {N_CALLS:,} calls, {total_steps:,} total steps, {elapsed:.1f}s ===")
print(f"(routed through the REAL Simulator/graph/telemetry -- not LatentPayload in isolation)")
print(f"(full replay-equivalence checked on {N_CALLS // REPLAY_SAMPLE_EVERY:,} sampled calls, 1 in {REPLAY_SAMPLE_EVERY})\n")

print("--- Violations (target: zero across the board) ---")
for k, v in violations.items():
    print(f"  {k}: {v}")

final_trust = np.array(final_trust); final_memory = np.array(final_memory)
print(f"\n--- Sanity: final trust/memory distributions still look like Tier-0-only run? ---")
print(f"  trust_scalar  mean={final_trust.mean():.4f} std={final_trust.std():.4f}")
print(f"  memory_flag   mean={final_memory.mean():.4f} std={final_memory.std():.4f}")

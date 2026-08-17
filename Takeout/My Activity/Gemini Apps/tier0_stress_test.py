import sys, time
sys.path.insert(0, "Latent")
sys.path.insert(0, "Domain")
import numpy as np
from LatentPayload import LatentPayload
from CallerState import DynamicState

N_CALLS = 250_000
rng = np.random.RandomState(42)

# 5 randomized variables -- resolution is now a per-step rate, can fire at
# any point, including multiple times per call, same structural shape as
# friction_rate and wait_overrun_rate.
call_lengths       = rng.randint(1, 16, size=N_CALLS)
friction_rates      = rng.uniform(0.0, 0.5, size=N_CALLS)
wait_overrun_rates  = rng.uniform(0.0, 0.5, size=N_CALLS)
expected_waits      = rng.uniform(10.0, 120.0, size=N_CALLS)
resolution_rates    = rng.uniform(0.0, 0.5, size=N_CALLS)   # CHANGED: per-step rate, not one end-of-call flag

violations = {
    "trust_bounds": 0, "volatility_bounds": 0, "memory_ceiling": 0,
    "memory_monotonic": 0, "friction_count_bounds": 0, "perceived_wait_bounds": 0,
}
final_trust, final_frust, final_memory, final_volatility, final_friction_count = ([] for _ in range(5))
max_consecutive_resolved = []
peak_trust_seen = []  # track the HIGHEST trust reached at any point mid-call, not just final

t0 = time.time()
for i in range(N_CALLS):
    lp = LatentPayload()
    cd = DynamicState()
    steps = call_lengths[i]
    frate = friction_rates[i]
    wrate = wait_overrun_rates[i]
    ewait = expected_waits[i]
    rrate = resolution_rates[i]
    prev_memory = 0.0
    consec = 0
    max_consec = 0
    peak_trust = lp.trust_scalar

    friction_rolls   = rng.uniform(0, 1, size=steps)
    wait_rolls       = rng.uniform(0, 1, size=steps)
    resolution_rolls = rng.uniform(0, 1, size=steps)

    for s in range(steps):
        cd.friction_event = 1 if friction_rolls[s] < frate else 0
        if wait_rolls[s] < wrate:
            cd.actual_wait = ewait * rng.uniform(1.1, 3.0)
        else:
            cd.actual_wait = ewait * rng.uniform(0.3, 1.0)
        cd.expected_wait = ewait
        cd.resolved = bool(resolution_rolls[s] < rrate)  # CHANGED: independent per-step roll

        consec = consec + 1 if cd.resolved else 0
        max_consec = max(max_consec, consec)

        lp.update_after_step(cd)
        peak_trust = max(peak_trust, lp.trust_scalar)

        if not (0.0 <= lp.trust_scalar <= 1.0): violations["trust_bounds"] += 1
        if not (0.0 <= lp.volatility <= 1.0): violations["volatility_bounds"] += 1
        if lp.memory_flag > 1.0: violations["memory_ceiling"] += 1
        if lp.memory_flag < prev_memory: violations["memory_monotonic"] += 1
        prev_memory = lp.memory_flag
        if not (0 <= lp.friction_count <= lp._FRICTION_CAP): violations["friction_count_bounds"] += 1
        if not (0.0 <= cd.perceived_wait <= 1.0): violations["perceived_wait_bounds"] += 1

    final_trust.append(lp.trust_scalar)
    final_frust.append(cd.frustration)
    final_memory.append(lp.memory_flag)
    final_volatility.append(lp.volatility)
    final_friction_count.append(lp.friction_count)
    max_consecutive_resolved.append(max_consec)
    peak_trust_seen.append(peak_trust)

elapsed = time.time() - t0
total_steps = int(call_lengths.sum())

print(f"=== TIER 0 STRESS TEST v2: {N_CALLS:,} calls, {total_steps:,} total steps, {elapsed:.1f}s ===")
print("(resolution now an independent per-step roll -- can occur any number of times, anywhere in the call)\n")

print("--- Constraint violations (target: zero) ---")
for k, v in violations.items():
    print(f"  {k}: {v}")

final_trust = np.array(final_trust); final_frust = np.array(final_frust)
final_memory = np.array(final_memory); final_volatility = np.array(final_volatility)
final_friction_count = np.array(final_friction_count)
max_consecutive_resolved = np.array(max_consecutive_resolved)
peak_trust_seen = np.array(peak_trust_seen)

print("\n--- Final-state distributions ---")
for name, arr in [("trust_scalar", final_trust), ("frustration", final_frust),
                   ("memory_flag", final_memory), ("volatility", final_volatility),
                   ("friction_count", final_friction_count)]:
    print(f"  {name:16s} mean={arr.mean():.4f} std={arr.std():.4f} min={arr.min():.4f} max={arr.max():.4f}")

print("\n--- Does trust actually reach the ceiling under sustained resolution? ---")
print(f"  peak trust_scalar seen at ANY point, across all calls: max={peak_trust_seen.max():.4f}")
print(f"  max consecutive resolved steps in a single call, across population: {max_consecutive_resolved.max()}")
top = np.argsort(-max_consecutive_resolved)[:1][0]
print(f"  the call with the most consecutive resolved steps had {max_consecutive_resolved[top]} in a row, "
      f"trust_baseline={LatentPayload().trust_baseline} -> peak_trust_seen for that population: {peak_trust_seen[max_consecutive_resolved >= max_consecutive_resolved.max()-1].max():.4f}")

print("\n--- Correlations ---")
print(f"  friction_rate vs final trust_scalar:   r={np.corrcoef(friction_rates, final_trust)[0,1]:.4f}")
print(f"  resolution_rate vs final trust_scalar: r={np.corrcoef(resolution_rates, final_trust)[0,1]:.4f}  (expect positive, now testable for real)")
print(f"  resolution_rate vs peak trust seen:    r={np.corrcoef(resolution_rates, peak_trust_seen)[0,1]:.4f}")

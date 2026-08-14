# Iceberg Session Handoff — 2026-07-03

This is a handoff from a same-day session — read this before touching
anything new. Full project background (mantra, architecture, prior
corrections) lives in memory and in `SCORECARD.md`/`CHANGES.md` inside the
repo itself; this document covers only what happened THIS session,
additively. Verify against the attached code before trusting anything
below — same discipline this project has always used.

## What this session verified, by execution, not by re-reading docs

- **PRODUCTION_READINESS.md does not exist in either uploaded archive**
  (`Iceberg_full_repo.zip`, `Iceberg_flat.zip`). A *different* document
  titled "Iceberg Production Readiness Scorecard — 2026-07-03" was pasted
  in-chat later and read/cross-checked, but it is not confirmed saved to
  the repo under that filename. Resolve this naming/existence question
  before assuming either document is "the" production-readiness file.
- **Engine (Tier 0, `LatentPayload`)**: fuzz suite actually run (not just
  its `@settings` decorator read) — 4,000 examples across 3 test functions,
  9.6s, all passed. A from-scratch determinism script (not their test
  harness) confirmed byte-identical structural hash, state dict, and raw
  ledger across two independent runs.
- **Drivetrain (Tier 1)**: 55 tests across `Simulator`/`ReplayEngine`/
  `ClusterRunner`/graph files, run individually, all passed.
- **Transmission (Tier 2, PPO/MARL)**: `test_distressed_queue_dominates_triage`
  (the real end-to-end proof test) run directly — passes. All 9
  `test_integration_loop.py` tests passed, including bit-identical-ledger
  determinism and full replay-from-ledger-alone reconstruction.
- **Full suite**: 108 passed, 1 skipped, reproducible on both archives —
  EXCEPT the full-repo archive throws 1 collection error (see below).

## Discrepancies found this session — none fixed in the repo itself, all still open

1. **Stale `staffing_rl` files**: `conftest.py` and `SCORECARD.md` both
   assert `Engines/staffing_rl.py` / `Tests/test_staffing_rl.py` were
   deleted 2026-07-02. The **flat** distribution matches that claim
   (absent, clean run). The **full-repo** distribution still has both
   files, causing a real collection error. Open question carried over
   from earlier in the session, still unresolved: delete them from the
   full-repo copy, or leave as-is.
2. **`SCORECARD.md`'s PPOEngine citation is stale**: claims it consumes
   `QueueStress.compute_queue_loads()`. It doesn't — grepped, confirmed
   absent near PPOEngine anywhere. What's actually wired (in
   `Loop/IntegrationLoop.py`) is `PathCongestion.compute_path_congestion()`,
   the Round-5 replacement. The underlying claim (real per-caller data
   flows into PPO) is true and verified; only the function name in the
   scorecard prose is wrong.
3. **`rl_ppo.py`'s docstring is stale**: says the composite congestion
   weighting is "still an open modeling choice, not decided here." It
   isn't open — `PathCongestion.py`, built the same day, already hardcodes
   fixed weights (`W_FRUSTRATION = 0.30`, etc.).

None of these are functional bugs. All three are cosmetic doc/comment
drift, worth a cleanup pass, low priority relative to everything below.

## Built this session: the ingestion adapter (`IngestAdapter.py`, attached)

Purpose: translate a raw call-event log (timestamps + node arrivals, shaped
like a real telephony export) into the friction stimuli fields the real
engine already consumes (`friction_event`, `actual_wait`, `expected_wait`,
`resolved`) — the on-ramp for real data, buildable without a real
partner since the translation logic itself doesn't depend on which
platform eventually supplies the log.

**Two real bugs found and fixed this session, by tracing actual per-hop
output, not by review:**
- `actual_wait` was cumulative across the whole call — one early hold
  re-tripped the engine's `actual > expected` gate on every later hop.
  Fixed: now per-hop, attributed to the node where the wait happened.
- The dwell-anomaly gate used raw inter-menu timestamp gaps, which
  **included** hold time — so a long hold double-fired both the adapter's
  own `friction_event` gate AND the engine's separate `expected_wait` gate
  for the same wait. Fixed: dwell is now net transit time with holds
  subtracted out, so the two gates are independent as intended.

**Confirmed working end-to-end** (clean/overrun/hangup profiles) through
the real `Simulator`/`IntegrationLoop`/`PPOEngine` — deterministic,
verified twice from scratch.

**Explicitly NOT working**: the "revisit" profile (caller backtracks to an
already-seen node). The real graph has no back-edges — `journey_next()` is
fixed and directional per Correction 1, so a raw log's revisit hops have
nowhere to land when mapped 1:1 onto real simulator ticks; verified by
execution that they get silently dropped past the caller's actual
(shorter) real termination point. **This is the scoped Fable handoff
below — approved, not yet sent.**

## Built this session: expected_wait calibration study (`calibrate_expected_wait.py`, attached)

The original question ("what should the `expected_wait` threshold be?")
turned out to be unanswerable in the abstract — no ground truth for
"reasonable." Reframed to a measurable question: **which expected_wait
policy makes the engine's own `peak_frustration` signal best separate
callers who abandon from callers who complete, using only signal accrued
before termination?**

Built a 1,000-caller behavioral cohort where abandonment is *caused* —
each caller draws a latent patience tolerance; wait accumulates; crossing
tolerance triggers abandonment (with two confounders kept in: patient
long-waiters who complete despite big waits, and a small wait-innocent
random-hazard hangup rate, i.e. "life happens"). Then ran multiple
`expected_wait` policies — flat constants, per-node empirical percentiles,
and an oracle (uses ground-truth remaining tolerance, unobservable in
reality) — through the **real** engine and scored each by AUC.

**Key results:**
- Theoretical ceiling given the wait-innocent abandoners in this cohort:
  AUC ≈ 0.856. The oracle scored 0.853 — the method measures exactly what's
  measurable; the gap to 1.0 is irreducible by design.
- Observable methods (no ground truth available) cap around **AUC ≈ 0.73**
  (`flat_30s`, `node_p50`, `node_p75` all cluster there).
- Percentile choice is an **operating-point dial, not a quality dial**:
  `node_p50` catches 74% of future abandoners at a 30% false-flag cost on
  completers; `flat_30s` catches 60% at 13.5% false-flag cost. Same AUC,
  different triage-budget trade-off — a business decision, not a stats one.
- **Counter to my own expectation going in**: per-node normalization did
  NOT dominate flat constants. In this cohort, abandonment is driven by
  *cumulative* wait vs. personal tolerance — node-blind — so per-node
  normalization strips out exactly the magnitude signal that predicts
  leaving. Whether real callers behave this way is unknown without real
  data.
- **Actual conclusion**: `expected_wait` isn't a constant to pick — it's an
  **observe-phase calibrated artifact**. This calibrator gets *stronger* on
  real data (real logs carry abandonment labels for free, no synthetic
  behavioral coupling needed) and slots directly into the Target Manifest
  observe → lock lifecycle.

Caveats carried forward: the flat-vs-per-node result is specific to this
generator's assumptions and must be re-measured on real data, not ported
as a conclusion; revisit-pattern calls are excluded from this cohort until
the Fable mapping task lands; the gate is binary per hit (magnitude-blind),
which is what caps observable AUC near 0.73 — a cumulative-expectation
variant is buildable adapter-side without touching the engine, but is a
governance-relevant design lever for a deliberate future decision, not
something to build unilaterally.

## Fable handoff — approved, drafted, NOT yet sent

Scoped problem: how backtrack/revisit friction from a raw call log gets
attributed onto the real graph's fixed, directional journey (no back-edges
exist). Full prompt with hard constraints, required red/blue process, and
worked-example requirement was drafted and approved earlier this session.
**Needs your explicit go before it gets sent to a new Fable chat** — per
your standing instruction, this doesn't happen automatically.

## Immediate open items, not yet decided

- Resolve the `staffing_rl` file discrepancy (delete from full-repo copy,
  or leave as-is).
- Clean up the two stale doc/docstring citations (#2, #3 above).
- Resolve the `PRODUCTION_READINESS.md` naming/existence question.
- Send the Fable revisit-mapping prompt (or revise it first) — your call.
- Decide whether `IngestAdapter.py` and the calibrator get formally added
  to the actual repo as real modules, or stay sandbox tools for now.
- The cumulative-expectation gate variant flagged above — real lever,
  deliberately not built without your sign-off.

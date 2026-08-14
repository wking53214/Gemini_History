# Sentinel Diagnostic Engine — Find Where Containment Leaks

The **second component of the Sentinel build**, and the thing you run on day one
of an engagement. It takes caller journeys (from the harness now, real client logs
later) plus the observed caller attributes, and discovers **which kinds of callers
are bailing, where containment is fake, and whether any of it tracks a protected
attribute** — all from the data, by reverse-engineering the segments rather than
being told them.

## What it does, and the boundary it holds

It **finds and describes** leaks. It does **not** prescribe a fix. "Re-sequence
this menu" is the simulator + prescription layer, built later. Keeping "I found a
problem" separate from "here is the fix" is a deliberate honesty boundary: the
diagnostic is allowed to be confident about *where* the leak is precisely because
it does not over-reach into *what to do*, which requires simulation.

It produces three things:

1. **The containment-honesty decomposition.** Not just "containment is 40%," but:
   of that 40%, how much is *real* (resolved) vs *fake* (left automation
   unresolved, will call back). On the reference data, containment is ~40% but
   **18% of that is fake** — the number a dashboard hides, because it counts a
   fake-contained call and a real one identically.
2. **Segment leak discovery** — which caller segments leak containment, in two
   trust tiers (below).
3. **A disparate-impact scan** — whether any protected group has a materially
   worse containment experience or worse live-agent access.

## The two-tier hybrid (the core design)

The central choice: **trust level is structural.** A `Finding` and a `Candidate`
are *different types*, not the same object with a flag, so a speculative pattern
can never be confused for a solid one.

| Tier | Type | Source | Trust |
|------|------|--------|-------|
| 1 | `Finding` | Transparent single + pairwise scan | **Shippable.** Human-legible ("phone + fraud callers contain at 22%"), directly checkable. A ghost is unlikely at this granularity and easy to spot. |
| 2 | `Candidate` | Recursive interaction tree (depth ≥ 3) | **Lead, not finding.** Finds the deeper interactions the scan misses, but deep interaction-mining is where ghosts breed — so nothing here is a finding. Each carries the metadata the Partner needs, with empty verdict slots. |

**Why not one blended list?** Blending mixes the tree's ghosts with the scan's
solid ground and loses the ability to tell them apart — worse than either method
alone. Separation by type makes the trust level un-confusable.

**The two methods cross-check each other.** A tree candidate whose driving
attribute also shows up in the scan is more plausible (`corroborated_by_scan =
True`); one the scan sees no trace of is explicitly labeled a ghost risk. This is
a cheap first plausibility filter, before the real Partner validation exists.

## The design decisions, and why

**Why reverse-engineer the segment instead of being told it.** A real engagement
cannot see *why* a caller behaves as they do; it sees *who they are* (the
company's records) and infers the rest. The engine never reads the harness's
hidden disposition — it searches the observed attributes for the grouping that
explains the bailing, exactly as a consultant must. That is the valuable, hard
part, and the harness is built so the engine cannot cheat.

**Why findings are capped at pairwise.** A single- or two-attribute segment is
transparent and a client's own people can sanity-check it. Anything deeper is, by
construction, harder to trust and goes in Tier 2. The cap is what makes Tier 1
shippable.

**Why the tree is a simple recursive split, not a black-box model.** A black-box
model surfacing unexplainable segments would itself violate the honesty
discipline — you cannot put "the model says so" in front of a client. The tree
produces candidates that are readable paths of `attribute=value` splits, so even a
lead is explainable.

**Why nothing is "client-ready" out of this engine.** A `Candidate.client_ready`
is true *only* when validation says REAL and fairness says CLEAN — both filled by
the future Partner. Fresh from the engine, every candidate is `UNASSESSED` and not
client-ready. The engine generates; the Partner validates. The seam is real so the
Partner plugs in cleanly.

**Why the engine looks at protected attributes even though it never optimizes on
them.** This is the subtle, important one. The optimization scan uses only
behavioral/contextual attributes — it will never recommend treating a protected
group differently. But a *separate* disparate-impact scan measures containment and
agent-access across protected groups specifically, to **detect inequity the system
would otherwise be blind to**. Detecting disparate impact is the opposite of
creating it. (An earlier version optimized-excluded protected attributes and was
therefore blind to a real planted disparity — a genuine flaw, now fixed: see
DECISIONS ADR-014.)

## What it shows (verified)

On 12,000 callers through the reference tree:

- **Finds the planted leak:** the worst finding is `phone & fraud` at ~22%
  containment, ~15 points below overall — exactly the planted fraud/distress
  effect, surfaced as a transparent, checkable finding.
- **Decomposes honestly:** ~18% of "contained" calls are fake (unresolved).
- **Catches planted disparate impact:** with a deliberately planted protected
  disparity, the scan flags `protected_group=True` with worse containment AND
  worse agent access. Without a planted disparity, it stays silent (no false
  alarm).
- **Keeps tiers clean:** candidates never self-certify; 0 are client-ready out of
  the engine.

## What this is NOT

- **Not the prescription engine.** It describes leaks; it does not fix them.
- **Not a validator.** Every finding and candidate is a *candidate for the
  Partner*. The engine does first-pass fairness flagging only; the full
  disparate-impact audit and the validation (real vs ghost, replication) are the
  Partner's job.
- **Not calibrated.** All thresholds (`min_segment_support`, `finding_gap`,
  `tree_min_leaf`, …) are illustrative defaults that behave sensibly on the
  reference data, not validated against a real contact center.

## Run

```bash
python3 run_diagnostic.py            # full report on a clean population
python3 run_diagnostic.py --bias     # plant a protected disparity; watch the scan catch it
python3 -m pytest test_diagnostic.py     # 14 tests
```

Pure standard library (the engine itself needs no numpy; the harness it consumes
does). 

## Tests (14, all passing)

Decomposition (real vs fake adds up, fake is real and nonzero); discovery (scan
finds the planted leak; findings are legible singles/pairs; candidates are deep
interactions); tier discipline (findings/candidates are distinct types; no
candidate is client-ready without the Partner; the partner seam is present;
candidates are cross-checked against the scan); fairness (disparate impact caught
when planted, no false alarm when not, protected attributes never optimization
targets, scan only optimizes on behavioral keys); robustness (missing attributes
excluded not crashed, empty run no crash).

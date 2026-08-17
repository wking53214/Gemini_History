# Sentinel Prescription Layer — Confidence-Stated Recommendations, or an Honest Refusal

The **fourth component of the Sentinel build**, and the most honesty-critical,
because this is the component that produces the number a **client** sees. The
governing rule, straight from the build brief: a bare "+8%" is a credibility bomb.
Every recommendation here carries not just a projected lift but **how much to trust
it** — and changes that do not earn trust are refused, openly.

## What it does

It takes proposed structural changes and, for each one:

1. **Measures the full-population effect** (via the simulator) and **refuses
   anything that is not a clean win.** A false win or a landmine never becomes a
   recommendation — it is `REJECTED_NOT_CLEAN`.
2. For a clean win, it does **not** trust the single number. It runs
   **hold-out-and-replicate**: split the population into folds, measure the change
   independently on each, and check whether the effect holds. A change whose effect
   does not replicate is `REJECTED_GHOST` — caught and refused, not shipped.
3. It expresses confidence as a **band plus a categorical level with a
   rationale** — replication strength + support + seed sensitivity — never a lone
   percentage.
4. Nothing is **client-ready** until the Partner fills `validation = REAL` and
   `fairness = CLEAN`.
5. It records what was projected so a real post-implementation outcome can be
   scored **HIT / PARTIAL / MISS** — the feedback loop.

## Why hold-out-and-replicate (and not a hand-waved %)

A projected lift is only trustworthy if it is **stable**. Measuring the same change
on independent subsamples answers, empirically: *"if you'd had only a fraction of
this data, what range of answers would you have gotten?"* If every fold agrees in
sign and the spread is tight, the effect is robust. If the folds disagree, the
full-population number was an artifact. This is a real, interpretable uncertainty —
not theater.

It is paired with **seed sensitivity** (re-running under different behavioral RNG)
to check robustness to noise. Both are stated honestly, and neither claims the
formal statistical-confidence-interval rigor we do not have — the band is described
as an *empirical hold-out spread*, explicitly.

**This caught a real ghost.** "Lead with the balance option" measures as a +0.4pt
clean win on the full population — a naive tool would report it as a small win. The
replication test found that only 2 of 5 folds shared the sign; the rest flipped.
Correctly labeled `REJECTED_GHOST`: the full-population number was noise. That is
the credibility-bomb defense working on a naturally occurring ghost, not a
contrived one.

## Three structural honesty devices

**Confidence is a band, not a number.** `ConfidenceAssessment` carries the per-fold
estimates, the spread, the seed band, the support, and a level with a plain-
language rationale. The point estimate never travels alone. Rendered:

```
projected +1.7pt containment [hold-out folds +1.1 to +2.9pt;
seeds +1.7 to +2.0pt; support 12000]. Confidence: MODERATE.
```

**Rejection is structural.** A `Prescription.status` is one of
`REJECTED_NOT_CLEAN` (simulator says false win / landmine / no improvement),
`REJECTED_GHOST` (clean win that fails replication), or `CANDIDATE` (clean win that
replicates). A ghost can never be mistaken for a live recommendation.

**The Partner seam + client-ready gate.** Every prescription carries
`validation_verdict` and `fairness_verdict`, empty by default. `client_ready` is
true only when status is `CANDIDATE` AND confidence is not GHOST/NO_EFFECT AND
validation is REAL AND fairness is CLEAN. The honest default is never client-ready.

## The confidence levels

| Level | Meaning | Prescribable? |
|-------|---------|---------------|
| `NO_EFFECT` | full-population effect below the meaningful floor | No |
| `GHOST` | does not replicate across folds (sign flips) | No — rejected |
| `LOW` | replicates in sign but unstable / thin support | Yes, flagged low |
| `MODERATE` | replicates with moderate spread, decent support | Yes |
| `HIGH` | replicates tightly, large support, stable across seeds | Yes |

The classifier (`classify_confidence`) is a **pure function** of the fold deltas,
seed deltas, and support — so every level boundary and the ghost path are
deterministically unit-tested with hand-crafted inputs, independent of any
simulation.

## The feedback loop

`PrescriptionOutcome` records the projected delta and band. After the client
implements the change and the actual containment movement is measured,
`.score(actual)` classifies it:

- **HIT** — actual landed within the projected band.
- **PARTIAL** — same direction, outside the band.
- **MISS** — wrong direction, or no movement.

Misses are recorded openly. The honesty discipline has to survive being wrong in
front of a client; over many engagements, this is how the tool earns trust and how
its confidence calibration improves.

## What this is NOT

- **Not an optimizer.** It assesses changes you propose; it does not search for
  them.
- **Not the Partner.** It does its own replication-based honesty check, but the
  formal, independent validation and the disparate-impact audit are the Partner's
  job — and client-ready requires both.
- **Not calibrated.** The classification thresholds (`MIN_MEANINGFUL_DELTA`,
  spread cutoffs, `LARGE_SUPPORT`, fold count, seeds) are illustrative, sensible
  defaults, not validated against a real contact center.

## Run

```bash
python3 run_prescription.py              # candidates, rejections, bands, feedback loop
python3 -m pytest test_prescription.py       # 16 tests
```

Pure standard library (orchestrates the simulator, which consumes the harness).

## Tests (16, all passing)

Confidence classifier unit tests (no-effect floor, ghost on sign-flip, HIGH when
tight+supported, MODERATE on wider spread, LOW on thin support, caveats always
present); gating (clean win -> candidate, false win -> rejected-not-clean,
non-replicating clean win -> rejected-ghost); honesty of output (confidence is a
band, candidate not client-ready without Partner, partner seam present); feedback
loop (HIT, PARTIAL, MISS x2).

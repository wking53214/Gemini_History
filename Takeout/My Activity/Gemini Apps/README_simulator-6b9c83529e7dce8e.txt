# Sentinel Simulator — Honest Measurement of Proposed IVR Changes

The **third component of the Sentinel build**, and the one that makes the thesis
*actionable without making it dangerous*. The diagnostic engine finds where
containment leaks; the simulator answers the next question: **"if I change the tree
this way, what happens to everyone?"** — including the segment a change might hurt.

## What it does, and the trap it refuses to fall into

It measures the whole-population effect of a proposed structural change by running
a **controlled comparison**: the same population through the baseline tree and
through the changed tree, with deterministic traversal, so any difference is
attributable to the *structure*, not noise.

The thing that makes it honest: **the net number is never the whole story.** The
danger is a change that lifts containment on average while wrecking a segment —
"+10% on 25% of callers, but 5% now go agent-only." A simulator that reported only
the net would say "ship it." This one decomposes the effect across segments and
**surfaces harm at the top level**, right next to the headline, so it cannot be
missed.

## The two failure modes it catches

| Verdict | What it means | Why a naive tool misses it |
|---------|---------------|---------------------------|
| **FALSE WIN** | Containment rose largely by raising *fake* containment — trapping more callers in unresolved self-service. | A naive tool watches only top-line containment, which counts fake and real alike. This watches true resolution and fake containment *separately*. |
| **LANDMINE** | Net gain, but a segment is materially harmed (containment down, or forced to an agent, or trapped in fake containment). | A naive tool reports the average. This reports the *distribution*. |

Plus **CLEAN WIN** (net containment and true resolution both up, no segment
harmed), **MARGINAL**, and **NO IMPROVEMENT**.

## Verified: the simulator refuses a seductive bad change

On the reference tree, a change that reroutes dispute-call failures to a "we've
filed it, goodbye" dead-end produces:

```
net containment +6.8pt   <- looks like a big win
  true resolution +3.3pt
  fake containment +3.5pt  <- HALF the "gain" is fake
verdict: FALSE WIN — containment rose largely by trapping more callers in
         unresolved self-service. Not a real gain.
  HARM: 12 segment(s) hurt
```

A simulator that watched only net containment would have recommended this change.
This one calls it what it is. That single behavior is the reason the component
exists.

## The design decisions, and why

**Why the distribution is first-class (not a drill-down).** `harmful_segments` and
`worst_harm` sit on the result object right beside `net_containment_delta`. If
someone reads only the headline, the harm is still in their face. Burying the
distribution one layer down would let the landmine hide, which defeats the purpose.

**Why every effect is measured on BOTH containment and true resolution.** A change
can raise containment by raising *fake* containment. Watching only containment
would reward exactly the wrong thing. Watching true resolution separately is what
turns a "+6.8pt" into a correctly-labeled FALSE WIN.

**Why a clean win requires a conjunction.** `is_clean_win` is true only when net
containment is up AND net true resolution is up AND fake containment is not
materially up AND no segment is harmed. A net gain with a harmed segment is
explicitly *not* clean. The conjunction is the honesty.

**Why the comparison is deterministic per caller.** Each caller's RNG is seeded by
their id, so the same caller behaves identically across the baseline and variant
trees. Without this, a measured delta could be RNG noise rather than the effect of
the change, and the measurement would be meaningless.

**Why a change must return a clone (and is rejected if it doesn't).** The
comparison relies on the baseline staying fixed. A "change" that mutated the
baseline in place would corrupt the comparison, so the simulator rejects any change
that returns the same tree object.

**Why it MEASURES but does not SEARCH.** Auto-searching the space of possible
re-sequencings is deferred on purpose: an optimizer chasing a net number is exactly
how you *find* the landmine change. Auto-search needs the validation Partner and
hard distributional guardrails before it is safe; measurement of human-proposed
changes is unambiguously useful now. (See DECISIONS ADR-019.)

**Why it measures but does not PRESCRIBE.** Turning a clean measured win into a
client-facing recommendation, with calibrated confidence (hold-out-and-replicate),
is the prescription layer's job. The simulator hands up an honest measurement; the
prescription layer decides what is solid enough to put in front of a client. Each
boundary keeps the next component honest.

## What this is NOT

- **Not an optimizer.** It measures changes you propose; it does not search for
  them. That is deferred until the Partner and harm-constraints exist.
- **Not a prescription engine.** It produces a measurement and a verdict, not a
  client-facing recommendation with confidence.
- **Not calibrated.** `SEGMENT_HARM_THRESHOLD` and the segment cuts are
  illustrative, sensible-on-the-reference-data defaults, not validated against a
  real contact center.

## Run

```bash
python3 run_simulator.py             # three changes: a clean win, a marginal one, a false win
python3 -m pytest test_simulator.py      # 11 tests
```

Pure standard library (consumes the harness, which uses numpy).

## Tests (11, all passing)

Controlled comparison (no-op yields zero effect; baseline not mutated; a
non-cloning change is rejected; determinism). Honest verdicts (clean win
recognized; FALSE WIN caught; harmed segments surfaced). Distribution is
first-class (per-segment effects computed; a net gain with a harmed segment is NOT
a clean win; `compare` ranks clean wins above higher-net landmines; no-improvement
verdict).

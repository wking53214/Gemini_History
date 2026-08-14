# Sentinel Harness — The Causally-Wired Synthetic World

This is the **first component of the Sentinel build**: a synthetic caller
population and a configurable IVR tree, wired so that **caller emotion and tree
structure jointly determine whether a call contains or bails** — through rules
that are written down explicitly, so that the diagnostic engine built next can be
*proven* to recover them.

## Why this exists (and why it is built first)

The whole Sentinel thesis is "re-arrange the IVR and change containment, because
caller psychology controls the outcome." To build and honestly prove an engine
that *discovers* that relationship, you first need data where the relationship is
**real and known**. Prior rule-clean synthetic data showed nothing, because
routing was correct by construction and signals were uniform over time — there
was no pattern to find. This harness fixes that the honest way: it plants a
genuine causal structure and writes it down, so "the engine found X" can be
checked against "X is what we planted."

This is the **development substrate** for everything downstream and the
**prospect demo** for the consulting practice. It is not the product; it is the
world the product is tested in.

## The three pieces

| File | What it is | The key idea |
|------|-----------|--------------|
| `ivr_tree.py` | The configurable IVR structure | A tree of nodes; a MENU is an **ordered** list of options. Re-sequencing = permuting that order. Mutable and `clone()`-able so structure can be varied without touching the original. This is the shared spine the future simulator also uses. |
| `caller_model.py` | The synthetic population | Each caller has a **hidden disposition** (patience, base temperature, self-serve affinity) and **observed attributes** (age, product, tenure, channel, reason…). Observed attributes *correlate* with disposition without *being* it — so the pattern must be reverse-engineered, not read off a flag. |
| `traversal.py` | The behavioral engine | Runs a caller through a tree with **emotion evolving at each step**. Sequence becomes consequence: the same caller, run through two orderings, can contain in one and bail in the other, because each node changes their temperature and temperature drives the next choice. |

Plus `reference_tree.py` (a sample tree with a known anti-pattern and real
fake-containment dead-ends) and `test_harness.py` (locks structure, determinism,
and the causal claims).

## The design decisions, and why each was made

**Why the tree is a mutable, clone-able structure (not a hard-coded flow).**
The core intervention is "re-sequence the menu and measure the change," which
means the tree must be something you can *vary* from the first line. `clone()`
and `reorder_menu()` exist so the future simulator can compare current-vs-variant
on the same population and attribute any difference to *structure*, not to having
rebuilt the flow. Hard-coding the tree would mean rebuilding it later.

**Why emotion evolves along the path (not a fixed attribute).**
If emotion were a fixed stamp on a caller, sequence could not matter — the order
of nodes would be irrelevant. The whole thesis requires that passing through a
node *changes* the caller, so that a distressed caller acknowledged early cools
and contains, while the same caller buried under three menus heats up and bails.
Emotion is therefore a `temperature` that accumulates heat (effort, irrelevant
menus, failed self-serve, dead-air dips, auth loops) and sheds it (resolution,
early acknowledgment). The trajectory is the mechanism; sequence is the lever.

**Why disposition is hidden and attributes only correlate with it.**
A real engagement cannot see why a caller behaves as they do; it sees who they
are (the company's records) and has to infer the rest. If the harness exposed a
`will_contain` flag, the diagnostic engine could cheat and we would prove nothing.
So the causal driver (disposition) is hidden, and observed attributes correlate
with it through documented rules (repeat callers run hot; fraud/dispute reasons
run hot; mobile/web channel raises self-serve affinity; legacy product lowers it).
The engine must recover the pattern by reverse-engineering, exactly as in reality.

**Why the route-intent-vs-outcome gap is built in.**
Containment counts a call that left automation — whether or not it was actually
*resolved*. The dangerous lie is a call that *looks* contained but bounced (the
caller will call back). The harness plants this: some self-serve nodes have
`resolve_prob < 1`, and crucially, some route an unresolved caller to a terminal
"we've handled it, goodbye" node rather than to an agent. That produces real
`CONTAINED_UNRESOLVED` outcomes, so containment (40%) visibly exceeds true
resolution (32.5%). Without this gap there would be no lie for the system to find.

**Why the protected attribute has no effect by default (but can be planted).**
The fairness boundary is absolute: optimize on behavior and context, never on
protected identity. The harness encodes this by making the protected-style marker
causally inert by default — so the future fairness auditor can be tested for
*false alarms* (it should find nothing) — while `plant_protected_bias=True`
injects a real identity-linked disparity so the auditor can also be proven to
*catch* one. The harness can create the disease on purpose so the auditor is
testable; it never ships the disease on by default.

**Why traversal is deterministic per (population, tree, seed).**
The simulator will compare two trees on the same population and must attribute the
difference to *structure*, not RNG noise. So each caller gets a private,
reproducible RNG derived from the seed and their id; the same caller behaves
identically across tree variants. The intervention test relies on this.

## What it shows (verified)

On a 5,000-caller population through the reference tree:

| Metric | Reference (agent option **first**) | Re-sequenced (agent **last**) |
|--------|-----------------------------------|-------------------------------|
| Containment | 40.0% | 41.6% |
| True resolution | 32.5% | 34.5% |
| Fake containment | 7.5% | 7.0% |

- **Sequence is causal:** pushing the agent option last lifts containment and true
  resolution on the *same* population (difference is purely structural).
- **Emotion drives outcome:** cool callers contain at ~46%, hot callers at ~29% —
  a 16-point gap through the identical tree.
- **The planted reason effect is recoverable:** fraud/dispute callers contain far
  worse than balance/payment, as planted — a pattern the diagnostic engine should
  later discover.

**Honest note on effect size.** The single-menu re-order moves containment only
~1.6 points. That is *correct* and deliberate: one menu change should not be a
miracle, and a harness that claimed +20% from one tweak would be dishonest. The
larger, emotion-conditioned, multi-node lifts are what the simulation engine will
search for later. The modest, believable effect is a feature.

## What this is NOT

- It is **not** the diagnostic engine, the simulator, or the prescription layer —
  those are later components. This is the world they will be built and tested in.
- It is **not** calibrated against real contact-center data. Every behavioral
  constant (`BehaviorParams`) and every causal rule is an **illustrative,
  documented** choice that produces sensible behavior, not a validated model.
  Labeled as such throughout.
- It does **not** model the workforce side (occupancy, AHT, shrinkage). Sentinel
  is the IVR instrument; the harness reflects that scope.

## Run

```bash
python3 reference_tree.py        # smoke demo: containment before/after a re-sequence
python3 -m pytest test_harness.py    # 12 tests: structure, determinism, causal claims
```

Pure standard library plus **numpy** (sampling and weighted choice). No other
runtime dependency.

## Tests (12, all passing)

Structure/plumbing: tree validation, dangling-edge rejection, non-mutating
re-sequence, traversal determinism, population reproducibility, hidden-disposition
non-leakage. Causal claims: sequence changes containment, emotion drives outcome,
fake containment actually occurs, the planted reason-effect is recoverable, no
protected disparity by default, planted protected bias is detectable when enabled.

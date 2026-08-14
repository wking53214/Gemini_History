# Lever Registry Specification

**Status:** Design spec, stasis (not yet implemented)
**Depends on:** Target Manifest spec (reuses its declare/recommend discipline)
**Blocks:** The change-governance layer (concrete diff -> declare -> deploy -> measure)
sketched alongside this spec -- you cannot produce a valid concrete diff without
first knowing what dimensions are actually changeable.

---

## 0. Why this exists

Every recommendation Iceberg can generate, menu order, prompt wording, timing,
routing paths, is worthless if the business has no mechanism to act on it.
Worse than worthless: a recommendation phrased as actionable, against a lever
the platform doesn't actually expose, is a false promise dressed as insight.

The deeper problem: Iceberg cannot assume it knows, in advance, what any given
IVR platform allows a business to control. A platform built ten years ago
didn't anticipate AI-driven routing as a concept. A platform built next year
will expose levers nobody has thought of yet. Iceberg's core cannot be
rewritten every time a new lever type is invented -- that's not scalable
governance, that's a maintenance trap.

The Lever Registry is the mechanism that lets Iceberg know what's actually
changeable on a given deployment, and stay open to lever types that don't
exist yet, without ever touching Iceberg's core code to add them.

---

## 1. The core move: levers are data Iceberg reads, not types it knows about

If "menu reordering," "prompt timing," "wording variants" are hardcoded
categories inside Iceberg's own logic, every genuinely new lever type requires
a code change to Iceberg itself. That's the wrong shape and doesn't survive
contact with "no one had any clue ten years ago AI would be involved in IVR
work."

Instead: a **Lever Registry** is a declared, structured description of what a
specific platform allows, that Iceberg reads at runtime. Matching a finding to
a recommendation becomes data-driven lookup, not hardcoded category logic.

### Lever entry schema

```
{
  "lever_id": "menu_intent_menu_order",
  "platform": "monster_router_3000",
  "shape": "ordered_list",              // see closed shape vocabulary, §2
  "current_value": ["billing", "tech", "cancel", "sales", ...],
  "addresses_friction_types": ["menu_depth", "navigation_priority"],  // open vocabulary, §2
  "constraints": { "max_items": 9 },    // shape-specific, optional
  "registered_at": "...",
  "registered_by": "...",
  "status": "active"                    // active | deprecated | removed
}
```

`addresses_friction_types` is the field that makes this extensible rather than
merely configurable. Without it, Iceberg's core still has to hardcode "menu-
depth friction gets fixed by reordering-type levers." With it, the matching
is: find any *currently registered* lever tagged as addressing the friction
type just found, regardless of whether that lever type existed when Iceberg
was built.

---

## 2. What's closed versus what's open

This distinction is the whole design, get it backwards and the registry
either can't extend or can't be reasoned about at all.

**Closed (small, fixed, deliberately boring):** the `shape` vocabulary --
`ordered_list`, `numeric_range`, `boolean`, `enum`, `free_text`. These are
primitive data shapes, not domain concepts. Nearly any control a platform
could ever expose reduces to one of these. Low churn, foundational, fine to
fix.

**Open (genuinely unbounded, expected to grow forever):**
`addresses_friction_types` and `lever_id` namespaces are free strings, not an
enum Iceberg's core validates against. A lever tagged `"addresses_friction_types":
["ai_disclosure_timing"]` works today even though that friction type didn't
exist in anyone's vocabulary five years ago -- nothing in Iceberg needed to
change to accept it.

---

## 3. Two tiers: platform registry and deployment registry

A lever registry entry is really two things layered together, and conflating
them wastes the most valuable part of this design:

- **Platform-level registry**: what Monster Router 3000 is *capable* of
  exposing, in general. Built once per platform, reusable across every
  business running that platform. This is the same re-releasable-asset shape
  as the failure library from the IP conversation -- learn a platform's
  capabilities once, that knowledge pays out across every future customer on
  that platform, at near-zero marginal cost per new deployment.
- **Deployment-level registry**: which of the platform's available levers
  *this specific business* has actually granted Iceberg control over. A
  business may not enable every lever their platform technically supports,
  for their own policy, contract, or risk reasons. This layer is thin,
  deployment-specific config -- the cassette, not the boombox, same split as
  the CallerState adapter discussion.

Iceberg reads the intersection: platform capability AND deployment grant.

---

## 4. Finding versus Recommendation, and the honest-gap rule

Two distinct things, and today's earlier recommendation list wrongly treated
them as one:

- **A Finding** -- "this path produces disproportionate frustration." Universal,
  platform-agnostic, purely a product of the friction engine already built.
  Requires no lever to exist.
- **A Recommendation** -- only ever drawable from levers *currently registered*
  for that specific deployment.

**Hard rule:** Iceberg must be able to surface a Finding with zero available
Recommendation, explicitly, rather than either staying silent or inventing a
recommendation against a lever that doesn't exist. "Here is a real, measured
problem; your platform currently gives you no registered control over it" is
a legitimate, honest output. Silently dropping the finding because there's no
lever to pair it with hides real information the business should have, even
if they can't act on it today -- it's also the strongest possible argument for
requesting a new lever from their platform vendor.

---

## 5. Connection to the change-governance layer

A concrete diff (from the change-governance sketch: "menu `intent_menu`,
reorder billing to position 1") is only expressible if `intent_menu`'s
`menu_order` lever is registered with `shape: ordered_list`. The Lever
Registry is the prerequisite vocabulary the diff format is written in -- not
a fifth new system, the missing first step underneath the four already
sketched (diff, declare, deploy, measure).

The Target Manifest's Recommendation/Declaration split applies unchanged: a
Recommendation record can now reference a specific `lever_id` and a proposed
new value; a Declaration is the business approving that specific, concrete
change. Same hashed, versioned discipline, narrower and more concrete scope
than the Manifest's original threshold-setting use.

---

## 6. Registry versioning

What a platform allows changes over time -- a vendor adds an API, a business's
contract changes, a lever gets deprecated. Registry entries carry `status`
(`active`/`deprecated`/`removed`) rather than being silently deleted, same
discipline as everything else in this codebase: a removed lever is a recorded
event, not an erased one. A Finding that previously had a matching
Recommendation can lose it if the underlying lever is deprecated -- that's a
real, visible state change worth surfacing, not something to paper over.

---

## 7. What this spec does NOT decide (explicitly deferred)

- Who actually populates a platform-level registry -- a person doing
  onboarding/integration work, or an automated adapter reading a platform's
  own capability API where one exists. Likely both, depending on the
  platform; not an engineering call to make unilaterally.
- Storage/schema mechanics (same as the Target Manifest -- unspecified here).
- Whether a business can register a *false* capability (claiming a lever
  exists when it doesn't) and what governance response that deserves. Real
  question, not addressed by this spec.
- Any actual platform integration work. This spec defines the shape of the
  registry, not a single real platform's contents.

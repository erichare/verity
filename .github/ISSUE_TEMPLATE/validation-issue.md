---
name: Validation issue
about: Challenge or question a published validation number
title: "[validation] "
labels: validation
assignees: ''
---

<!--
Verity's validation numbers are meant to be challenged. Every figure we publish
is registered, protocol-labeled, and recomputable from committed data in
docs/headline-numbers.md. If a number looks wrong, doesn't reproduce, or is
being quoted without its protocol label somewhere, this is the place.
-->

## Which number

The exact figure you are challenging (value + metric), and where you saw it
(README, whitepaper, verity.codes page, report PDF, talk/slide, …).

> Example: "Bullet lands Cllr 0.205 ± 0.125 quoted on the benchmark page."

## Which protocol label

Every published number carries one of the protocol labels from
[`docs/headline-numbers.md`](../../docs/headline-numbers.md):

- [ ] In-sample (deployed reference) — *not a validation claim by definition*
- [ ] Source-disjoint (whitepaper / cmr_table)
- [ ] Frozen benchmark (`bullets-v1` / `cartridge-v1` / `toolmark-v1`)
- [ ] Single study / specialist baseline
- [ ] The number was quoted **without** a protocol label (that alone is a bug —
      tell us where)

## Reproduction attempted?

- [ ] Yes — describe exactly what you ran (commands, commit SHA, dataset/kit
      version, seed) and paste the numbers you got
- [ ] No — explain the concern instead (methodological objection, apparent
      inconsistency between two published figures, suspected label mix-up, …)

For the frozen benchmark, the replication kit from data.verity.codes pins the
pairs, folds, and scoring; please include the kit/split id if you used it.

## Expected vs observed

| | Published | Yours / expected |
|---|---|---|
| Metric (Cllr / AUC / …) | | |
| Protocol | | |

## Additional context

Anything else — environment, data provenance, related literature.

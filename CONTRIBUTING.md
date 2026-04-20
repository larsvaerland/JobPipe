# Contributing

Thanks for your interest in JobPipe.

This is a solo-led project with active cleanup and restructuring underway. Focused contributions are welcome, but the main expectation is that changes strengthen the current product direction instead of widening scope.

## Read this first

Before making non-trivial changes, read:

1. [MASTER_PLAN.md](MASTER_PLAN.md)
2. [PRODUCT_VISION.md](PRODUCT_VISION.md)
3. [ROADMAP.md](ROADMAP.md)
4. [OSS_SCOPE.md](OSS_SCOPE.md)
5. [DEPENDENCY_POLICY.md](DEPENDENCY_POLICY.md)
6. [specs/architecture-boundaries.md](specs/architecture-boundaries.md)

Then use the relevant docs in `docs/` and active specs in `specs/`.

## What JobPipe is trying to be

JobPipe should stay:

- candidate-first
- hiring-aware where that improves candidate outcomes
- local-first
- structured
- traceable
- narrow in scope and strong in reasoning
- genuinely useful as a public OSS framework/toolkit

It should not drift into:

- recruiter-product scope
- ATS parity
- broad workflow automation
- generic AI copilot features
- speculative feature sprawl
- open-core ambiguity inside the public repo

## Good contribution areas

- bug fixes
- setup clarity
- runtime-boundary cleanup
- documentation consistency
- connector-boundary cleanup
- dashboard/report usability
- better error handling
- focused workflow improvements that reinforce the core model
- public examples, fixtures, and showcase surfaces
- dependency cleanup that improves OSS operability without weakening the current scope

## Before opening a PR

Please:

- explain the problem being solved
- keep the change focused
- avoid mixing feature work and unrelated refactors
- update documentation when terminology, behavior, or structure changes
- align the change with the current roadmap and active specs

## Pull request expectations

A good PR should explain:

- what changed
- why it changed
- trade-offs or risks
- how it was validated
- which docs/specs were updated

## Documentation rule

If a change affects behavior, terminology, planning direction, or structure, update the relevant docs in the same change.

The repo should not carry competing explanations of:

- what JobPipe is
- what the next build sequence is
- which docs are canonical
- which names are transitional versus canonical
- what belongs in the public repo versus a later private layer

## Public repo boundary

This repo should be treated as the public JobPipe foundation.

Good public contributions strengthen:

- canonical models
- local-first runtime behavior
- generic adapters and projections
- tests, fixtures, examples, and docs

Do not widen this repo toward:

- recruiter-product workflows
- premium-only business logic
- speculative private-layer packaging hidden in the public tree

## Style expectations

- prefer small, reviewable diffs
- keep logic readable
- avoid unnecessary dependencies
- preserve traceability
- do not widen scope casually

## Dependency rule

For generic concerns, prefer maintained OSS modules with permissive licenses and clear documentation.

Avoid introducing dependencies that would make a later private/commercial layer harder to maintain or license cleanly unless the trade-off is explicitly justified.

## Notes on active specs

Not all specs are equal.

Current active next-build specs are centered around:

- architecture boundaries
- canonical data model
- job claims
- hiring-side selection signals
- controlled CV tailoring
- candidate narrative profiles

Later strategic specs should not be treated as immediate implementation targets unless the roadmap or current task says so.

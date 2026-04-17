# Boundary Map

## Purpose

This document defines the working split between the public `JobPipe` repository and the later private `JobPipe Workbench` repository.

The goal is clarity, not secrecy theater:

- keep the public repo genuinely useful
- keep the private repo focused on real business-critical logic
- avoid duplicated code and fuzzy ownership

## Default Rule

Keep something public when it is generic, reusable, and improves the OSS foundation.

Keep something private when it is:

- tuned to business-specific workflow
- based on proprietary calibration or evaluation logic
- operationally sensitive
- tied to commercial packaging

## What Stays Public

These belong in `JobPipe`:

- local-first runtime foundations
- generic ingestion and normalization logic
- pipeline orchestration and public workflow scaffolding
- reusable evaluation helpers
- dashboard and export mechanisms that are useful on their own
- public docs, examples, templates, and extension surfaces
- generic Gmail/status tracking behavior that is not moat-critical

## What Moves Or Starts Private

These belong in `JobPipe Workbench`:

- tuned decision-policy packs
- proprietary ranking and prioritization heuristics
- calibration logic tied to private outcome patterns
- premium workflow packaging and product-specific UX logic
- sensitive or brittle connectors that create operational risk
- private evaluation corpora, regression fixtures, and benchmark cases
- commercial product flows that do not improve the OSS foundation directly

## Borderline Cases

These need judgment:

- a generic utility discovered while building private workflow should usually be pushed back to public
- a generic connector helper belongs public; a sensitive connector implementation may stay private
- a public interface can stay public even when its best policy pack stays private
- docs about the public model belong public; docs about private operating logic belong private

## Current Repo Implication

The current public codebase still contains implementation that may later support private workflow indirectly.

That does not mean the public repo should be hollowed out now. The split should be:

- additive
- deliberate
- based on actual differentiation

## Anti-Patterns

Do not:

- fork the public repo into the private repo and let them drift
- keep “secret” product logic in hidden folders inside the public repo
- move generic utility code private just to make the public repo weaker
- duplicate shared code when a public interface or shared contract would do

## Practical Rule For New Work

When adding new logic, ask:

1. Is this generic and reusable?
2. Does publishing it weaken the business meaningfully?
3. Does it improve the public OSS foundation?

If it is generic and useful, it should stay public.

If it is tuned, proprietary, or commercially sensitive, it should live in `JobPipe Workbench`.

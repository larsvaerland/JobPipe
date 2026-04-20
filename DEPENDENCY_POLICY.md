# Dependency Policy

**Last updated:** 2026-04-17

This file defines the dependency and license direction for the current public JobPipe repo.

The public repo is being aligned as a real OSS-first framework/toolkit. Dependency choices should support that public role **and** avoid creating problems for a later private/commercial layer built on top.

Use this file together with [specs/architecture-boundaries.md](specs/architecture-boundaries.md): the architecture spec defines where capabilities should live, and this policy defines when to use OSS directly, when to wrap it, and when to build custom.

## Current license position

The current public repo remains MIT-licensed in this phase.

This file does not change the repo license. It sets the policy direction for choosing dependencies and shaping the public foundation responsibly.

## Dependency goals

Prefer dependencies that are:

- actively maintained
- clearly documented
- widely understood
- easy to operate as a solo maintainer
- stable enough for a long-lived local-first tool
- compatible with a future private/commercial layer

## Preferred license families

Prefer:

- MIT
- BSD-2 / BSD-3
- Apache-2.0
- ISC
- PSF

These are the best fit for the public repo and a later private layer that should compose with it cleanly.

## Use OSS directly for generic concerns

Use maintained OSS directly when the capability is generic infrastructure rather than a source of differentiation.

Examples:

- schema validation
- relational storage and migrations
- CLI/runtime ergonomics
- HTTP and parsing utilities
- templating
- testing and observability

## Wrap or compose OSS where JobPipe should own the abstraction

Use maintained OSS behind a JobPipe-owned boundary when the repo should keep control of the interface.

Examples:

- scheduling and background runners
- LLM and agent runtimes
- document rendering backends
- provider-specific integration helpers

The public repo should avoid exposing a third-party runtime as the product’s canonical contract surface.

## Build custom where differentiation lives

Build and own the parts that are most likely to become durable product value.

Examples:

- canonical candidate/job/evaluation model
- job claims
- hiring-aware decision tables and selection signals
- candidate evidence units
- candidate narrative profiles
- watchlists and change-event semantics
- calibration and premium workflow logic

## Avoid

Avoid introducing foundational dependencies that are:

- unlicensed
- weakly maintained
- poorly documented
- operationally heavy without clear payoff
- incompatible with a later private/commercial layer

Avoid restrictive license families in the public foundation unless there is an explicit high-value reason:

- GPL
- AGPL
- SSPL
- BSL and similar source-available licenses

Also avoid defaulting to:

- vector-database-first infrastructure
- large workflow/orchestration platforms that eclipse the local-first control plane
- framework churn for aesthetic reasons

## Practical rule for this repo

For generic concerns:

- prefer maintained permissive OSS

For core product meaning:

- prefer JobPipe-owned interfaces and models

For any new dependency:

1. justify the problem it solves
2. explain why the capability is generic or differentiating
3. note the license family
4. explain whether it should be used directly, wrapped, or avoided later
5. state which public package slice should own the dependency boundary

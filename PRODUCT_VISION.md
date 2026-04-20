# JobPipe Product Vision

**Last updated:** 2026-04-17

## Core product thesis

JobPipe should help a candidate identify and act on the jobs they are genuinely competitive for, not just the jobs they already know how to search for.

Public category for this phase:

- **career intelligence workbench**

Plain-language fallback:

- **job-search decision system**

The product is most useful when it does four things well:

- turns messy job ads into structured claims and explicit decisions
- helps the candidate understand what is actually winnable
- helps the candidate explain adjacent or non-obvious fit credibly
- keeps watching the market so useful change reaches the user quickly

The product mechanism is not "AI content generation." It is:

**evidence-backed decision support with living monitoring**

## Who the product is for now

JobPipe is for a serious, privacy-conscious job seeker who needs better judgment, not more job listings.

The current reference user is Lars, which is useful because it forces the system to solve real workflow problems instead of generic ones.

The target user shape for this phase is:

- active search or meaningful career pivot
- knowledge work or adjacent professional roles
- too much noise in the market
- non-obvious fit across titles, domains, or role families
- need for credible positioning, not just keyword stuffing

## Why it matters

The hard part of job search is often not finding jobs.

It is:

- deciding what is actually worth pursuing
- understanding why a role is plausible or not
- making adjacent experience legible
- keeping attention focused over a long, noisy search

Existing tools often optimize for:

- more applications
- prettier documents
- faster generic AI text
- more workflow surface area

JobPipe should optimize for:

- fewer bad pursuits
- better prioritization
- stronger candidate-specific explanations
- better reuse of the same evidence and state across the whole workflow

## Current wedge

The current wedge is the candidate-first decision workbench.

That means:

1. ingest jobs and leads
2. filter weak matches cheaply
3. reason about fit, selection risk, and explainability
4. preserve state, follow-up, and outcome history
5. generate candidate-facing decision surfaces and evidence-backed application support

That wedge is intentionally narrower than a broad career platform.

## Public and future product shape

For current public positioning:

- `JobPipe` should remain the umbrella and OSS/framework name
- the public repo should be a real OSS framework/toolkit, not a crippled teaser

For later business packaging:

- a future private/commercial implementation may be packaged as **JobPipe Workbench**

The public and later private layers should share the same core product truth, not tell different stories.

## Candidate-first but hiring-aware

JobPipe should stay candidate-first.

But it should stop being blind to how roles are actually filtered and judged.

That means the product should explicitly account for:

- structural gates
- recruiter screening behavior
- title and domain continuity bias
- ambiguity tolerance
- evidence burden

This is not recruiter-product scope.

It is candidate-side realism.

The product should get better at distinguishing:

- substantively plausible roles
- procedurally winnable roles

and should help the candidate see the gap between those when it matters.

## Product shape

JobPipe is best understood as:

- a local-first data-and-reasoning layer
- packaged as a candidate-facing workbench

That means:

- data is the product
- connectors are adapters
- dashboards and external tools are projections
- AI is a bounded interpretation layer, not the product itself

This also means JobPipe should not chase value through surface breadth alone.

It also means the public repo should be able to stand on its own as a useful local-first toolkit even before any later private split exists.

## What differentiates it

The differentiator is not "AI writes application text."

The stronger differentiation is:

- job claims instead of opaque ad blobs
- explicit decision support instead of one blended score
- candidate evidence units instead of ad hoc resume rewriting
- narrative profiles instead of regenerated identity stories
- watchlists and change events instead of repeated manual rescanning
- local feedback and outcome history instead of stateless prompts

In short:

**JobPipe should know why a job matters, why it does not, and what changed.**

## What it is not

JobPipe is not:

- a recruiter platform
- an ATS replacement
- a broad automation suite
- a generic AI copilot
- a mass application engine
- a broad connector product
- a full resume-builder business
- an open-core teaser without standalone OSS value

Those directions weaken the wedge by turning a data-and-reasoning product into a surface-area race.

## Success criteria

The product is moving in the right direction if it becomes true that:

- the candidate sees fewer but better opportunities
- adjacent roles become easier to trust and explain
- decision quality improves because the evidence is inspectable
- the product becomes more useful over time through monitoring and feedback
- the same core state improves intake, prioritization, follow-up, and tailoring

## Near-term strategic truth

The near-term product foundation is now:

1. job claims
2. hiring-aware decision support
3. candidate evidence units
4. candidate narrative profiles
5. watchlists and change events

That is the path to a product that stays narrow enough to build, but strong enough to compound.

# Jobpipe

*Reduce noise. Prioritize better. Follow up with structure.*

Jobpipe is a practical job search operating system for people who are tired of messy, repetitive, low-signal job hunting.

It helps turn a chaotic process into a structured workflow: find jobs, filter out the noise, focus on the listings that actually matter, and keep track of what happened next.

This started as a personal tool, but it is being shaped into something broader: a trustworthy workflow for job seekers who want better structure, clearer decisions, and less wasted effort.

---

## Why this exists

Modern job searching is noisy.

You open too many tabs. You scan too many weak matches. You lose time on jobs that were never a fit. You forget where you applied, what happened next, or why you decided something was worth pursuing in the first place.

Jobpipe exists to reduce that friction.

The goal is not to make job search feel flashy or fully automated. The goal is to make it **clearer, calmer, and more structured**.

---

## What Jobpipe does

Jobpipe helps with three parts of the process:

### 1. Triage
It gathers jobs from relevant sources and filters out obvious noise before deeper evaluation.

### 2. Prioritization
It helps identify which jobs deserve real attention, using staged evaluation instead of treating every listing the same.

### 3. Follow-up
It keeps decisions, outcomes, and status visible so the process does not disappear into notes, browser tabs, and inbox clutter.

---

## What Jobpipe is

- a practical workflow for job discovery, triage, and follow-up
- a product-minded solo project rooted in a real user problem
- a decision-support tool, not just a scraper or dashboard
- a structured way to reduce manual noise in the job search process

## What Jobpipe is not

- not a full ATS replacement
- not a mass auto-apply bot
- not a generic resume builder
- not a polished SaaS product
- not an attempt to replace human judgment with AI

---

## Product principles

Jobpipe is built around a few simple rules:

- **Cheap filters before expensive AI calls**
- **Traceable decisions over black-box magic**
- **Practical usefulness over feature bloat**
- **Human judgment stays in the loop**
- **A clearer workflow matters more than clever automation**

---

## How it works

Jobpipe follows a staged workflow designed to reduce noise before spending money or attention on deeper evaluation.

### 1. Collect jobs
Job listings are pulled from relevant sources and stored in a structured input format.

### 2. Filter early
Before any LLM call happens, Jobpipe applies a set of low-cost filters:
- geographic filtering
- title-based exclusion rules
- semantic pre-filtering against the candidate profile

This removes a large share of irrelevant listings at effectively zero cost.

### 3. Triage and score
Jobs that pass the early filters go through deeper evaluation:
- AI-assisted triage
- structured parsing of requirements
- profile matching
- pivot scoring
- deterministic moderation into final decision tiers

### 4. Generate useful outputs
For stronger matches, Jobpipe produces structured outputs such as:
- decision data
- scoring breakdowns
- dashboard-ready reports
- application support materials

### 5. Track follow-up
Where enabled, Gmail integration helps detect confirmations, interviews, and rejections so application follow-up stays visible over time.

**Core principle:** cheap filters run before expensive AI calls, so cost and effort are concentrated on jobs that are more likely to matter.

**Traceability:** every reviewed job leaves a structured artifact trail, so decisions can be inspected instead of treated like black-box output.

---

## Quick start

**Requirements:** Python 3.11+, OpenAI API key, and optional Google access for feed and Gmail features.

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .
copy .env.example .env
copy profile_pack.example.md profile_pack.md
```

Then update:
- `.env` with your API and source settings
- `profile_pack.md` with your own role targets, geography, and profile details

Run the pipeline:

```powershell
.\go.ps1
```

Useful options:

```powershell
.\go.ps1 -DryRun
.\go.ps1 -NoOpen
```

For detailed setup and optional Gmail integration, see:
- [docs/configuration.md](docs/configuration.md)
- [docs/decision-model.md](docs/decision-model.md)
- [docs/artifacts.md](docs/artifacts.md)
- [docs/profile-pack.md](docs/profile-pack.md)
- [docs/cli.md](docs/cli.md)
- [docs/architecture.md](docs/architecture.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Current status

Jobpipe is an actively evolving solo-built project.

It is already useful as a real workflow tool, but it is still growing in clarity, scope, and usability.

The current priority is to make it:
- easier to understand
- easier to trust
- easier to run
- easier to improve without losing structure

---

## Roadmap

See [ROADMAP.md](ROADMAP.md).

---

## Contributing

This project is currently solo-led, but feedback, ideas, and contributions are welcome.

Start here:
- [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT

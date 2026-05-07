# GitHub Project #6 — Field Defaults

Project: **JobPipe** (`https://github.com/users/larsvaerland/projects/6`)
Node ID: `PVT_kwHOCSFbLc4BJUda`

This document records the expected field defaults when triaging new issues. The
automation in `.github/workflows/project-intake.yml` adds new issues to the board
automatically; field values must be set manually during triage.

---

## Field reference

### Status
| Option | ID | Default for |
|---|---|---|
| Backlog | `f75ad846` | All newly opened issues |
| Ready | `61e4505c` | Issues fully specified and unblocked |
| In progress | `47fc9ee4` | Issues actively being worked |
| In review | — | Issues in PR review |
| Done | — | Closed issues |

**Default on intake:** Backlog

### Priority
| Option | Default for |
|---|---|
| P0 | Blocking active workflow (e.g. data loss, auth broken) |
| P1 | Core feature or sprint-planned work |
| P2 | Nice-to-have, deferred, or research |

**Default on intake:** P2 (triage upward during sprint planning)

### Size
| Option | Meaning |
|---|---|
| XS | < 1 hour, single file |
| S | 1–2 tasks, one session |
| M | 3–5 tasks, multi-session |
| L | 6+ tasks, consider splitting |
| XL | Full epic — must decompose before starting |

**Default on intake:** unset (set during triage)

### Type
| Option | Use |
|---|---|
| Epic | Large capability spanning multiple stories |
| Feature / Story | User-facing capability, one or more tasks |
| Task | Concrete implementation unit |
| Spike | Time-boxed research with written output |
| Bug | Broken behaviour, requires reproduction steps |

**Default on intake:** Task (override during triage)

### Area
| Option | Subsystem |
|---|---|
| Intake | Feed pull, connector merge, deduplication |
| Decisioning | Triage, parse, profile-match, moderate stages |
| Profile | Candidate profile, match dimensions |
| CV Authoring | Reactive Resume patch generation |
| Cover Letter | Cover letter generation and validation |
| JobSync | Companion shell integration |
| Calibration | Semantic filter, threshold, quality tuning |
| Planning | Docs, roadmap, sprint, governance |
| Infrastructure | Paths, server, CI/CD, packaging |
| Governance | Issue forms, project hygiene, automation |

**Default on intake:** unset (set during triage)

### Delegation
| Option | Meaning |
|---|---|
| Human-led | Requires human judgement or external access |
| Agent-ready | Fully specced, agent can implement autonomously |
| Needs decision | Blocked on a design or product decision |
| Research only | Output is a doc or recommendation, not code |

**Default on intake:** Needs decision (set to Agent-ready once fully specced)

---

## Triage checklist

When a new issue lands in Backlog:

1. Set **Type** (verify it matches the issue form used)
2. Set **Area** (which subsystem does it touch?)
3. Set **Priority** (P0/P1/P2)
4. Set **Size** (estimate tasks needed)
5. Set **Delegation** (can an agent run it, or does it need human input first?)
6. Move to **Ready** only when: acceptance criteria are clear, no blockers, all
   linked parent issues are closed or the dependency is explicit

---

## PR linkage hygiene

Pull requests are linked to issues via commit message references (`feat(#NN)`, `fix(#NN)`)
and GitHub's automatic keyword linking (`Closes #NN` in the PR body).

The `project-intake.yml` workflow only handles issues. PRs are linked manually:
- Include `Closes #NN` in the PR description for each resolved issue
- The project board card moves to Done automatically when the issue closes

To audit linkage gaps, use Issue #54 (board health check script) once implemented.

---

## Secrets required

| Secret | Scope | Used by |
|---|---|---|
| `PROJECT_PAT` | `project` (classic PAT) | `.github/workflows/project-intake.yml` |

Add this secret at: `https://github.com/larsvaerland/Jobpipe/settings/secrets/actions`

The PAT needs only the `project` OAuth scope — no write access to code or issues.

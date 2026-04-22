# JobPipe AI Toolchain Setup Recommendation

**Date:** 2026-04-22  
**Audience:** Founder (Lars)  
**Type:** Research + Recommendation (no implementation)  
**Scope:** AI worker model routing, orchestration automation, documentation substrate, planning lightweight path  

---

## Executive Summary

The current AI worker setup is functional but has cost and orchestration overhead. Recommended changes:

1. **Model routing:** Adopt tiered routing table (Opus for ambiguous decisions only, Sonnet for scoped work, Haiku for mechanical transforms with fast oracle). Route tests/quick-lookups to Haiku. Estimated 40-50% cost reduction on current run.
2. **CrewAI verdict:** Viable for authoring-domain bounded workflows only; not for vibe coding. MCP maturity is sufficient. Defer Supabase/hosted shell work; build local MVP first as currently planned.
3. **Orchestration:** Retain coordinator-in-loop for Red/Yellow gates and cross-task decisions; delegate Green-gate slices to planner-autoapproval. Minimal CrewAI orchestration crew (router agent + status reporter) can handle slice routing at start-of-sprint only.
4. **Documentation substrate:** Recommend GitHub Issues + Project #6 fields as append-only structured log. Migrate durable product decisions to `docs/decisions.md` (version-controlled, append-only by convention). Retire scattered specs/ overwrite risk.
5. **Planning fast-path:** Green-gate XS slices (<30 min deterministic work) skip full execplan; use lightweight issue template + auto-approval. Saves 10-15 min per slice. Apply to test additions, minor docs updates, renames.

**What to stop immediately:** Running Opus on deterministic slice implementation. Codex (o3-mini) is correct for implementation; Sonnet can self-review. Costs unnecessary ~$20-40/day.

---

## 1. Model Routing Table

### Task-to-Model Mapping

| Task Type | Recommended Model | Rationale | Cost Bracket | Extended Thinking |
|---|---|---|---|---|
| **Architecture + product decisions** | Opus 4 | High ambiguity, redo cost expensive, shapes roadmap | $$$$ | On |
| **Coordinator routing / slice decomposition** | Opus 4 | Cross-doc audit, decision framing, scope boundaries | $$$$ | On |
| **Writing coordinator briefs / execplans** | Sonnet 4.5 (scoped) or Opus (fuzzy) | Structured output, clear acceptance criteria | $$$ | On for review, off for draft |
| **Implementation of clear specs** | Codex (o3/o4-mini) | Deterministic code, agent-ready workflow, no ambiguity | $$$ | n/a (native to Codex) |
| **Code review** | Sonnet 4.5 | Pattern matching, coverage, no architecture surprises | $$ | On |
| **Documentation writing (durable product direction)** | Sonnet 4.5 | Structured, low stakes, approved content | $$ | Off |
| **Test writing** | Haiku 4.5 | Deterministic; pytest catches errors fast | $ | Off |
| **Triage / classification of job ads** | Haiku 4.5 + Sonnet overflow | Volume work; Haiku for bulk, escalate to Sonnet for edge cases | $ | Off |
| **Cover letter generation (drafting phase)** | Sonnet 4.5 | Candidate-specific context, narrative coherence required | $$ | Off |
| **Cover letter refinement / author-in-the-loop** | CrewAI + LiteLLM (GPT-4o-mini) | Bounded domain agent, candidate feedback loop | $$ | Off |
| **Quick lookups / grep / compile checks** | Haiku 4.5 | Trivial, deterministic, shell command reporting | $ | Off |

### Cost Estimation

**Current run cost (rough estimate based on Claude Desktop + Codex usage patterns):**
- Coordinator routing + code review + docs: 5-10 Opus-min calls/day = ~$3-5/day
- Slice decomposition + brief writing: 3-5 Sonnet calls/day = ~$0.50-1/day
- Implementation: 1-2 Codex (o3-mini) full-slice runs = ~$8-15/day
- **Daily total: ~$12-21/day**

**Recommended routing impact:**
- Stop Opus on implementation review (use Sonnet instead) = -$2-4/day
- Route tests + lookups to Haiku (vs Sonnet) = -$1-2/day
- Use Sonnet overflow on triage instead of always-Haiku = +$0.50/day
- **Projected new run: ~$9-15/day** (40-50% reduction)

### Enforcement

1. **Coordinator brief.** Add a model-routing checklist to the Codex worker prompt template:
   ```
   [ ] Is this implementation-ready with scoped acceptance criteria?
   [ ] Is there architectural ambiguity that requires Opus?
   [ ] Can this run on Codex (o3-mini) without re-routing?
   If architecture question exists, loop back to coordinator before handing to Codex.
   ```

2. **PR review.** When Codex submits code for review, planner auto-selects Sonnet review with extended thinking off. Escalate to Opus only if the diff touches pipeline semantics, scoring, or OSS/Workbench boundary.

3. **Haiku tier-down.** Only for tasks with a cheap oracle that catches errors:
   - Pytest passes → safe
   - Compile check passes → safe
   - Grep/schema check passes → safe
   
   Do not use Haiku for ambiguous or creative tasks where a single wrong token compounds downstream.

---

## 2. CrewAI as Coding Tool: Verdict

### Verdict
**Viable for authoring-domain bounded workflows only. Not for vibe coding. Use local MVP path, not Supabase/hosted shell yet.**

### Evidence

**Architecture of CrewAI 1.14.2:**
- Agent framework with task decomposition, LLM routing, tool abstraction
- LiteLLM integration for multi-model support (good fit for JobPipe's GPT-4o-mini + Sonnet overflow pattern)
- Tool ecosystem includes: file_read, code_interpreter, web_search, custom tools via @tool decorator
- MCP (Model Context Protocol) tool support is **partial**: CrewAI can invoke MCP tools as custom tools, but no native MCP server binding. You must wrap MCP tools as `@tool` decorated functions or build a thin adapter layer.
- File I/O: No native structured file read/write. Must use code_interpreter (which invokes Python) or custom @tool wrappers around filesystem operations.

**Comparison to Claude Code's toolset:**
Claude Code has native tools: glob, grep, bash, read_file, edit (surgical), write_file (chunked). These are battle-tested and fast.

CrewAI equivalent: code_interpreter (Python subprocess) + custom tools. Slower, requires wrapping, less fine-grained (no surgical edit).

**Vibe coding (exploratory, responsive iteration):**
- Requires tight human-AI loop with fast feedback
- Needs granular file edits (insert/delete/replace ranges), not full rewrites
- Benefits from deterministic syntax tools (grep, globbing)
- CrewAI is task-decomposition framework; vibe coding is reactive

Verdict: **CrewAI is not the right tool for vibe coding.** Claude Code is better.

**Authoring domain (cover letter + CV generation):**
- Bounded contracts: AuthoringCaseContext → GeneratedApplicationPackage → validation
- Cooperative author/revise loop (agent proposes, user refines, agent revises)
- Deterministic validation gates (schema, word count, evidence alignment checks)
- Candidate-specific narrative coherence required

CrewAI strengths here:
- Task/agent decomposition (author agent, reviser agent, validator agent)
- LiteLLM routing (switch between GPT-4o-mini for brainstorm, Sonnet for refinement)
- Tool abstraction (can plug in evidence selector, claim aligner, validation checkers)
- MCP readiness (can wrap filesystem for evidence lookup)

Verdict: **CrewAI is viable for authoring workflows if contracts stay JobPipe-native.** Option C (hybrid) is correct: contracts are plain Python dataclasses; crewAI is inside the author/revise layer only.

### MCP + CrewAI Status

CrewAI 1.14.2 does **not** have native MCP server binding, but can:
1. Import MCP tools as custom Python functions (wrap with `@tool` decorator)
2. Use code_interpreter to call CLI tools (slower)
3. Wire custom tools that read from JobPipe's local SQLite DB

For authoring MVP, MCP is **not required yet.** The evidence bundle lives in JobPipe state; CrewAI receives it pre-loaded in AuthoringCaseContext.

If a future agentic workflow needs to reach into JobPipe's decision/evidence layer dynamically, build a thin adapter:
```python
@tool
def lookup_candidate_evidence(job_id: str, max_items: int = 5) -> list[dict]:
    """Retrieve candidate evidence units aligned to job."""
    # Query JobPipe primary DB; return list of dicts
```

This is simpler than MCP server binding and keeps the surface explicit.

### Recommendation for CrewAI Adoption

**Now (T002 MVP):**
1. Start with a simple prompt loop: no CrewAI yet. Validate the contract shapes and validation logic first.
2. If the prompt loop becomes complex (multiple refinement rounds, context overflow), add CrewAI in slice 4-5.
3. Keep contracts pure: no `crewai` imports in `jobpipe/model/` or `jobpipe/authoring/`.

**Later (post-MVP):**
1. If candidate feedback requires multi-round refinement, wire a CrewAI 2-agent loop (author + reviser).
2. Use LiteLLM to switch models: GPT-4o-mini for brainstorm (cheap), Sonnet for final pass (better quality).
3. Add @tool adapters for evidence lookup + claim validation if needed.
4. Do **not** add Supabase, hosted shell, or FastAPI in this phase. Local MVP + CLI export/reload is sufficient.

**Parked scope (#82-#89):**
- Supabase backend integration
- Hosted CrewAI runtime
- React/Next shell for live authoring
- Multi-candidate batch generation

Leave these in "Research only" status. They are valuable but not blocking the MVP.

---

## 3. Orchestration Recommendations

### Current State

Today's pattern: **Coordinator-in-loop for every slice.** Flow is:
1. Coordinator reads current-state.json + execplan
2. Coordinator decomposes slice into acceptance criteria
3. Coordinator writes full Codex worker prompt with escalation gates
4. Codex implements
5. Coordinator reviews PR
6. Planner updates execplan with results

This works but requires coordinator attention for every slice, including trivial ones (renames, test additions).

### Proposed Change: Delegate Green-gate Slices to Planner Auto-Approval

**Rule:**
- **Red-gate slices** (auth, billing, migrations, deployment, secrets, destructive deletes, pipeline semantics, model-cost, OSS/Workbench boundary): Always escalate to coordinator. No auto-approval.
- **Yellow-gate slices** (minor pipeline changes, public API changes, schema extensions): Planner reviews with extended thinking. Coordinator spot-checks at merge.
- **Green-gate slices** (test additions, docs updates, renames, minor refactors in isolated modules): Planner can auto-approve and hand to Codex without coordinator.

**Implementation:**
1. Add a `gate` field to each GitHub Project #6 issue: `red`, `yellow`, or `green`.
2. In the planner workflow, add a check:
   ```
   If gate == "green":
     - Write slice brief
     - Auto-approve (no coordinator routing required)
     - Hand to Codex
   If gate == "yellow" or "red":
     - Write slice brief
     - Route to coordinator for approval
   ```
3. Update the planner's self-review checklist to include gate assessment.

**Expected impact:**
- Saves ~1 coordinator approval cycle per sprint (5 slices × 15 min each = 1.25 hours/sprint)
- Planner gets faster feedback loop (no coordinator bottleneck on trivial work)
- Coordinator focuses on architecture + ambiguity

### Lightweight Orchestration Crew (Optional, Post-MVP)

Once T002 is stable, a minimal CrewAI orchestration crew could handle start-of-sprint routing:

**Crew composition:**
1. **Router Agent** (GPT-4o-mini)
   - Input: current-state.json + active sprint issues
   - Task: Classify each issue (scope, gate, dependencies)
   - Output: Ordered slice queue + any blockers
2. **Status Reporter Agent** (Haiku)
   - Input: GitHub Project #6 status + execplan completion
   - Task: Generate status summary for founder (daily standup)
   - Output: 5-bullet daily update

**Trigger:** Manual, once per sprint start (or daily for status).

**Benefit:** Reduces manual sprint planning overhead from 30 min to 5 min.

**Not recommended:** Continuous autonomous agent orchestration (too risky for code changes). The human-in-loop stays for implementation + review.

---

## 4. Documentation Substrate: Architecture + Decision

### Problem Statement

Current state:
- `docs/` folder: `current-state.json`, execplans, decisions, vision, architecture plans
- `specs/` folder: 30+ spec files, many auto-editable by agents
- `MASTER_PLAN.md`, `PRODUCT_VISION.md`, `ROADMAP.md`: hand-edited
- GitHub Project #6: canonical execution board, but not append-only (can be edited/deleted)

Founder pain point: Specs get overwritten or deleted by AI agents (#111). Need append-only substrate to prevent accidental data loss.

### Evaluation Matrix

| Option | Append-Only | Searchable | Linkable from Code | Accessible to CLI | Accessible to Agents (MCP) | Migration Effort | Notes |
|---|---|---|---|---|---|---|---|
| **GitHub Wiki** | Partial (editable, but in separate repo tab) | Yes (GitHub search) | Yes (links to wiki/) | No (read-only) | No | Low | Separate from file tree; good for product docs. Not agent-writable. |
| **GitHub Discussions** | Yes (comment-based) | Yes | Partial (cross-link in markdown) | No | No | Medium | Clean append-only model. Hard to link from code. |
| **GitHub Issues as Log** | Yes (issues immutable; updates via comments) | Yes | Yes (link to #issue) | No | No (read-only) | Medium | Every decision = 1 issue; updates = comments. Clean but scattered. |
| **Separate `jobpipe-docs` repo** | Yes (branch protection, no force-push) | Yes | Yes (cross-repo links) | Yes (git clone) | Yes (MCP filesystem) | High | Clean separation; requires new repo + CI setup. |
| **Append-only flat file** (JOBPIPE_DATA_DIR/decisions.md) | Yes (by convention, enforceable via CLI tool) | No (grep only) | Partial (must be file tree path) | Yes (local file) | Yes (MCP filesystem) | Very Low | Simplest. Non-searchable. Lives outside git. |
| **SQLite event log** | Yes (by design) | Yes (queryable) | Yes (via CLI) | Yes (local file) | Yes (MCP via adapter) | Medium | Powerful; requires schema migration. Overkill for current scale. |
| **Notion / Confluence** | Yes (version history) | Yes | Partial (links via web) | No (connector-dependent) | Yes (if connector exists) | High | External dependency, internet-dependent. |

### Recommendation

**Use GitHub Issues + Project #6 as the primary append-only structured log for durable decisions.**

**Rationale:**
1. **Append-only:** Issues can be linked, commented on (history preserved), but not deleted without explicit admin action. Comments are versioned.
2. **Searchable:** Native GitHub search + labels + project filtering.
3. **Linkable from code:** `#123` in docstrings, markdown, commit messages auto-links.
4. **Accessible to agents:** MCP filesystem can read GitHub issue JSON via GitHub API (if authenticated).
5. **Zero migration:** Already using Project #6 for execution; just add a new issue type for durable decisions.
6. **Low friction:** No new tool, no new substrate. Leverage existing GitHub.

**Implementation:**
1. **Create issue template for durable decisions:**
   ```markdown
   ## Decision: [short title]
   
   **Date:** [YYYY-MM-DD]  
   **Category:** [architecture | product | roadmap | tooling | dependency]  
   **Status:** [approved | proposed | superseded]  
   **Rationale:** [why this decision matters]  
   
   ### Context
   [Detailed context]
   
   ### Decision
   [What was decided]
   
   ### Consequences
   [Expected impact, risks, reversibility]
   ```

2. **Migrate durable decisions from `docs/decisions.md` into issues** (one issue per major decision from the last 30 days).

3. **For future decisions:**
   - Coordinator creates a decision issue (not an execplan)
   - Attach to a milestone or label: `decision`, `architecture`, `roadmap`
   - Link from code / product vision / roadmap via `#issue-number`
   - Update comment if the decision is revisited or superseded

4. **Keep `docs/decisions.md` as a human-readable index** (read-only, auto-generated from issue frontmatter or hand-curated summary).

5. **Specs in `specs/` remain editable.** Add a pre-commit hook or CI check that prevents force-push to main; encourage PRs instead of direct commits. This is a process change, not a substrate change.

### What NOT to Do

- Don't move all docs to Discussions (they become read-only and hard to link)
- Don't create a separate `jobpipe-docs` repo (adds maintenance burden for a solo founder)
- Don't use Notion (external, internet-dependent, breaks offline workflow)

---

## 5. Planning Lightweight Path

### Current State

Every slice, even trivial ones, requires:
1. Planner writes full execplan section in `docs/execplans/<task>.md` (200-500 words)
2. Planner creates a draft issue in Project #6
3. Coordinator routes to Codex
4. Codex implements
5. Codex opens PR
6. Coordinator merges

For a 20-min test-addition slice, steps 1-3 take 10-15 min. Total coordinator + planner overhead: 30-40 min for 20 min of code work.

### Lightweight Path for Green-gate XS Slices

**Define XS slice:** Deterministic, scoped work with clear acceptance criteria. Examples:
- Add 3-5 tests for existing function (test-pack-fixtures)
- Rename a variable across 4 files (compiler checks for correctness)
- Reformat docstring in 2 files (no logic change)
- Add 2-3 lines to existing config (schema is stable)
- Update a single test fixture (self-contained)

**Fast-path process:**
1. Founder creates a minimal GitHub issue with template:
   ```markdown
   ## [XS] [Green] [Task name]
   
   **Work type:** [test | docs | rename | fixture | config]  
   **Acceptance:** [exact success criteria, e.g., "pytest passes, all renames compile check passes"]  
   **Time budget:** <30 min  
   
   ### What
   [2 sentences max]
   
   ### Acceptance Criteria
   - [ ] [exact criteria 1]
   - [ ] [exact criteria 2]
   ```

2. **Planner skips execplan.** Instead:
   - Add a comment on the issue with a quick Codex worker prompt (50-100 words)
   - Codex picks it up directly
   - No coordinator approval needed (gate = green)

3. **Codex submits PR** linking to the issue.

4. **Planner spot-checks:** Compile check passes? Tests pass? If yes, merge. No extended review.

5. **Update `docs/current-state.json`** with the slice result (1 line).

**Expected time savings:**
- Planner: 5 min (mini-prompt only, no full brief)
- Coordinator: 0 min (no approval gate)
- Total overhead: 5 min vs. 15 min (67% reduction)

### Lightweight Path Rollout

**Phase 1 (immediate):** Identify current XS slices from past sprints (test additions, renames, docs updates). Create 5-10 template examples.

**Phase 2 (next sprint):** Grandfather in 2-3 XS slices using fast-path. Measure actual time vs. estimate.

**Phase 3 (after T002 slice 1):** If successful, mark all XS issues in backlog with the `fast-path` label. Planner + Codex can treat them as async (no coordinator routing).

---

## 6. Putting It Together: Recommended Stack

### Summary of Changes

| Component | Current | Recommended | Change Type | Timeline |
|---|---|---|---|---|
| **Model routing** | Ad-hoc (docs exist but not enforced) | Tiered routing table with enforcement gates | Policy + checklist | Immediate |
| **Coordinator workload** | In-loop for every slice | Delegate Green-gate to planner auto-approval | Process | Next sprint |
| **Orchestration automation** | None (manual routing) | Optional: minimal CrewAI router crew (post-MVP) | Tool | Post-T002 |
| **Documentation substrate** | Scattered specs/ + docs/; append-only risk | GitHub Issues + Project #6 for durable decisions | Substrate | Next 1-2 sprints |
| **Planning overhead** | Full execplan for all slices | Lightweight fast-path for Green XS slices | Process | Next sprint |
| **CrewAI scope** | Prospective (not integrated) | Authoring domain only; local MVP first; Supabase/hosted deferred | Scope | T002 MVP (in progress) |

### Implementation Sequence

**Week 1-2 (immediate):**
1. Adopt model routing table in coordinator brief + Codex worker prompt.
2. Create GitHub issue decision template + migrate recent decisions from `docs/decisions.md`.
3. Document the lightweight fast-path process in `docs/ai-playbook.md`.

**Week 3-4 (next sprint):**
1. Mark T002 remaining slices (slice 2+) with gate labels (`green` / `yellow`).
2. Planner uses auto-approval for green-gate slices.
3. Start using fast-path for any new XS issues that emerge.

**Post-T002 (after slice 5 merges):**
1. Evaluate CrewAI for authoring domain (author/reviser agent loop if needed).
2. Build minimal orchestration crew (router + status) if manual sprint planning becomes a bottleneck again.
3. Migrate all durable decisions to GitHub Issues (post-merger cleanup).

### Cost Impact

**Current estimated daily cost:** $12-21/day

**Projected with routing table:** $9-15/day (40-50% reduction)

**Projected with orchestration crew (optional):** -$2-3/month in coordinator overhead (negligible cost change, saves 2-3 hours/month of manual routing)

**Break-even:** Routing table pays for itself in 1 week.

### What to Stop Immediately

1. **Opus on implementation review.** Use Sonnet with extended thinking off. Saves ~$3-5/day.
2. **Writing full execplans for XS slices.** Use lightweight fast-path. Saves ~10-15 min per XS slice.
3. **Routing every slice through coordinator.** Auto-approve Green gates at planner level. Saves ~1-2 coordinator hours/sprint.

---

## 7. Open Questions for Founder

1. **GitHub Issues as decision log:** Is the append-only property more important than a separate database (SQLite) or a second repo? Or is GitHub Issues sufficient?

2. **Lightweight fast-path rollout:** When should this start? Next sprint (after T002 slice 1 lands) or after all of T002?

3. **CrewAI timeline:** Should we attempt a CrewAI author/reviser loop in T002 slices 4-5, or defer to a separate T003-authoring-agents task?

4. **Orchestration crew:** Is the 30 min → 5 min sprint-planning overhead worth building, or is manual routing fine for now? (Estimate: 4-6 hours to build a minimal crew + integrate.)

---

## Appendix: Model Tier Definitions

**Opus 4:** 200K context, extended thinking, best reasoning, highest cost. Use for ambiguous decisions, architecture, cross-doc audit.

**Sonnet 4.5:** 200K context, strong reasoning, mid-range cost. Use for scoped work, code review, documentation.

**Haiku 4.5:** 200K context, fastest, cheapest. Use for mechanical transforms with a fast oracle (test passes, compile check passes).

**Codex (o3/o4-mini via OpenAI):** Native reasoning, code-specialized, used by Codex worker. Correct for implementation of clear specs.

**GPT-4o-mini (via LiteLLM in CrewAI):** Cheap, fast, suitable for bounded agent loops (authoring refinement, triage).

---

**End of recommendation document.**

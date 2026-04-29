# Shared MCP And Wrapper Contract — Execplan

**Goal:** Standardize how Axon, CodeGraphContext, Repomix, and GitNexus are
surfaced to Codex, Claude, and future CrewAI runtimes so tool usage is
consistent, low-friction, and low-token.

**Related issue:** `#140`

**Status:** Planning ready. This slice is about shared tool-interface policy
and thin wrapper design, not broad workflow redesign.

## Current State

### Already true

- GitHub is already a real connector/tool capability.
- GitNexus is already configured as an MCP server for Codex.
- Axon, CodeGraphContext, and Repomix are now configured as MCP servers for:
  - Codex (`C:\Users\larsv\.codex\config.toml`)
  - Claude Desktop
    (`C:\Users\larsv\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`)
- A shared MCP definition manifest now exists at:
  - `C:\Users\larsv\tool-evals\mcp\shared-mcp-servers.json`

### Still missing

- Fresh-session verification that Codex and Claude can actually see and call the
  MCPs after restart.
- One shared invocation contract so all agent runtimes call the same tool names,
  arguments, and outputs.
- An explicit CrewAI consumption path. CrewAI does not auto-inherit Codex or
  Claude MCP configs.

## Why This Slice Exists

Without a shared tool contract, the same machine ends up with:

- tools installed in one place
- MCP config living in another place
- repo docs describing usage in a third place
- future CrewAI agents forced to rediscover all of it

That causes drift, path confusion, and wasted tokens.

## Scope

### In Scope

- Verify the MCP entries for:
  - Axon
  - CodeGraphContext
  - Repomix
  - GitNexus
- Define the canonical trust order and fallback order.
- Define whether each tool is:
  - default
  - secondary
  - research-only
- Add a thin shared wrapper contract for future agent runtimes.
- Record how future CrewAI tools should read or reuse the shared manifest.

### Out of Scope

- Replacing the current MCP-enabled tools
- Broad CrewAI implementation
- Broad docs rewrite
- Repo-specific code refactors unrelated to tooling

## Recommended Contract

### Tool roles

1. **GitHub**
   - first-class connector/tool capability
   - preferred over raw `gh` when the connector exposes the needed operation

2. **Axon**
   - default structural graph tool
   - use for context, impact, dead-code candidate generation

3. **CodeGraphContext**
   - secondary graph tool
   - use for cross-check or alternate symbol/caller surface

4. **Repomix**
   - default context packer
   - use for bounded handoff and review packets

5. **GitNexus**
   - research-only on the current Windows-first workflow
   - keep configured, but non-default

### Trust order when answers disagree

1. direct code read
2. targeted repo search
3. tests and `python compile_check.py`
4. graph or packer output

### Shared manifest rule

`C:\Users\larsv\tool-evals\mcp\shared-mcp-servers.json` is the machine-level
source of truth for future runtime integration.

Codex and Claude may read their own app configs directly, but future CrewAI
tooling should consume this shared manifest or a thin wrapper layer derived from
it instead of inventing separate tool paths.

## Recommended Next Slice

### Phase 1 — Verification

1. restart Codex
2. restart Claude Desktop
3. verify each configured MCP appears and can answer a minimal request

### Phase 2 — Shared Wrapper Layer

Create a thin, stable wrapper surface for future agent runtimes. Keep it small.

Suggested commands:

- `axon-context`
- `axon-impact`
- `cgc-callers`
- `repomix-pack`

These may be PowerShell scripts or Python entrypoints, but they should:

- read the shared manifest or align exactly with it
- normalize output shape where helpful
- avoid repo-local path assumptions

### Phase 3 — CrewAI Consumption Rule

Document how the future Vibe coding crew and Job hunter crew should consume:

- the shared MCP manifest directly, or
- wrapper commands built from it

Default recommendation:

- Vibe coding crew should prefer wrappers or a shared tool adapter layer
- Job hunter crew should not depend on graph tools by default unless a concrete
  workflow actually benefits from them

## Acceptance Criteria

- Codex and Claude MCP visibility is verified in fresh sessions.
- Shared tool roles are explicit and stable.
- The shared manifest is treated as canonical for future runtime wiring.
- A wrapper contract is defined clearly enough for future CrewAI integration.
- Repo docs point at the real machine-level tool surface without contradiction.

## Validation

Minimum validation for this slice:

- confirm the MCP configs still parse and contain the expected server entries
- confirm fresh-session visibility for Codex and Claude
- confirm the shared manifest matches the actual configured commands

## Recommendation

Do not overbuild this into a new platform layer.

The right shape is:

- MCP where the tool already supports it
- one shared manifest for machine-level truth
- thin wrappers only where agent runtimes need a stable contract

That gives consistent behavior without turning tool setup into its own product.

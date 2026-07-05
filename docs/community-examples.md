# Community Examples

> Share your AllBrain setup! Open a PR or issue to add your example.

## Example 1: First install and verify

After running `uvx allbrain-agent-runtime install --codex` and restarting the client, a user's first terminal output looks like:

```text
$ uvx allbrain-agent-runtime install --codex --verify

✓ Codex config written to ~/.codex/config.json
✓ AllBrain MCP server found
✓ Handshake successful (55 tools available)
✓ Test event saved
✓ Event read back — content matches
✓ List events returns recorded event
✓ Resume project returns project state
✓ Shared memory is working
```

## Example 2: Two-agent handoff workflow

User opens two terminals, starts an agent in each, and observes shared memory:

**Terminal 1 — Agent A (codex):**

```text
save_event(type="task_planned", payload={"task": "implement auth"})
→ {"ok": true, "event_id": "01J5..."}
```

**Terminal 2 — Agent B (claude):**

```text
list_events()
→ [{"type": "task_planned", "agent": "codex", "payload": {"task": "implement auth"}}]

resume_project()
→ {"domain_event_count": 1, "agents": ["codex"]}
```

The event written by Agent A (Codex) is immediately visible to Agent B (Claude Code) without any export, file sharing, or manual handoff.

## Example 3: Conflict detection in action

```text
# Agent A writes a plan
save_event(type="plan_set", payload={"plan": "use Passport.js"})

# Agent B writes a conflicting plan  
save_event(type="plan_set", payload={"plan": "use Auth0"})

# Either agent checks for conflicts
detect_conflicts()
→ [{"type": "plan_set", "agents": ["codex", "claude"], "status": "conflict"}]
```

## Share your example

Submit a PR adding your terminal output, screenshot, or gist link. Guidelines:

- Anonymize any sensitive data (paths, tokens, project names).
- Include the AllBrain version (`allbrain --version` output).
- Describe your setup: single client, multi-agent, isolated vs shared database.

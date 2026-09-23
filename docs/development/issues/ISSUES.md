# ISSUES.md — Open Engineering Issues (tracked, not yet resolved)

_This file logs reproducible defects so they are not lost between sessions. Each entry is dated, scoped, and tagged with the DS-EO task it touches. Statuses: OPEN → RESEARCHING → RESOLVED._

---

## ISSUE-2026-0923 — `sessions_spawn` tool call drops its `args` (cannot dispatch subagents)

- **Status:** OPEN (manual workaround in use; deferred fix)
- **Date:** 2026-09-23
- **Touches:** TASK_MEE_013
- **Author:** PM (session `43de7ad2…`)

### Symptom
`sessions_spawn` fails every attempt with:

```
[tool error] {
  "status": "error",
  "tool": "tool_call",
  "error": "Invalid arguments for tool \"openclaw:core:sessions_spawn\": task: must have required property 'task'.
  Expected input: { task: string; agentId?: string; ... }"
}
```

Repeated calls produce identical empty-args errors. The model emits the tool call but the `args` object never reaches the validator.

### Verified (eliminate config/gateway as cause)
- `sessions_spawn` resolves as a live core tool with a valid schema (via `tool_describe`).
- `pm` agent `tools.allow` includes `"sessions_spawn"` (`~/.openclaw/openclaw.json`).
- `tools.agentToAgent.enabled: true`; all four agents (cto/implementer/reviewer/pm) allowed.
- `openclaw status`: gateway healthy on `ws://127.0.0.1:18789`, 4 agents, 189 sessions.
- Other tools (exec, read, write, tool_search, tool_describe) work normally in the same session.

### Root-cause hypothesis
The `sessions_spawn` **arguments are not transmitted through the `tool_call` wrapper on this session's model run**. Call reaches schema validation with an empty `args={}`, so the required `task` field is always missing. This looks like a **per-run call-serialization bug** (model/harness, not gateway or config), possibly tied to the specific model (currently `ollama/ornith-1.5:35b`).

### Workaround in use
Tasks are dispatched **manually** (operator spawns the subagent directly). TASK_MEE_013 artifacts (TASK_REQUEST.md, CTO_PLAN.md) are written and ready; the CTO review/implement/review/G4/G5 flow proceeds once subagent dispatch is unblocked or manually driven.

### Fix action items
- [ ] Reproduce with a single, minimal `sessions_spawn` (`task: "ping"`) on a fresh model run to isolate model vs. run.
- [ ] Test whether the same failure occurs for other subagent-targeting tools with required string fields.
- [ ] Check gateway/agent logs for a serialization/transport error preceding the rejection.
- [ ] Confirm whether it's the `ollama/ornith-1.5:35b` model specifically or a broader rollout.
- [ ] Once fixed, verify subagent dispatch resumes before closing this issue.

### Notes
Do **not** interpret "task" missing as "tool not allowed" — it is a payload-transport failure, not a policy block.

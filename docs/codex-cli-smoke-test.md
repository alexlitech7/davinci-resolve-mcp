# Codex CLI Smoke Test

This fork is configured for a conservative Resolve MCP proof of life:

- Read-only actions are allowed automatically when listed in `config/tool_policy.json`.
- Write, delete, and dangerous actions require confirmation.
- Resolve auto-launch is disabled by default. Open DaVinci Resolve Studio yourself before testing.
- The first write workflow is marker preview, then confirmed marker apply.

## Register The Server

From any trusted Codex workspace:

```bash
codex mcp add davinci-resolve -- python /Users/hejunli/workplace/davinci-resolve-mcp/src/server.py
```

If you use a virtual environment, point the command at that Python instead.

## Resolve Setup

1. Open DaVinci Resolve Studio.
2. Open a project.
3. Open or create a timeline.
4. Enable scripting in Resolve preferences if needed.

## End-To-End Demo

Ask Codex to call read-only tools first:

```text
Use the davinci-resolve MCP server to get the Resolve version,
current project, current timeline, and current timeline markers.
```

Then ask for a marker preview:

```text
Preview adding a blue timeline marker at the current playhead named
"Codex MCP smoke test" with note "Confirmed MCP marker write path."
Do not apply it yet.
```

The server should return `requires_confirmation`, an `operation_id`, and a
preview payload. To apply, ask Codex to call the same action with:

```json
{
  "confirm": true,
  "operation_id": "<operation_id from preview>"
}
```

The operation id is computed from the tool name, action, and non-confirmation
parameters. If any marker payload changes, the operation id changes and apply is
rejected.

## Policy File

The policy lives at:

```text
config/tool_policy.json
```

For v0, keep `allowlisted_writes` empty. Later, if you want selected write tools
to run without per-call confirmation, add exact `tool.action` names such as:

```json
"allowlisted_writes": ["timeline_markers.add"]
```

Only add allowlist entries after live testing the specific operation.

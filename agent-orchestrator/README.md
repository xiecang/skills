# agent-orchestrator

A Codex Skill for scoped delegation, dependency-aware parallel work and risk-based review in one main chat. [SKILL.md](SKILL.md) is the policy entrypoint. Maintaining this Skill does not start business orchestration.

## Requirements

Use the host's existing agent and progress-tracking capabilities. No dedicated runtime, memory provider, session registry or command hooks are required. Python 3.9+ is needed only for the optional candidate helper and maintenance tests. Follow user/project requirements for review tools; OCR delegate is otherwise optional.

## Validate

From this directory:

```bash
python3 -m unittest discover -s tests
```

The optional candidate helper's tests use temporary Git worktrees and real commands, including process-group cleanup. Independent decision scenarios live in `tests/role_scenarios.json`; [forward-test instructions](tests/role_forward_test.md) explain how to obtain fresh answers without showing the grader's expectations. Grade them with:

```bash
ORCHESTRATOR_ROLE_RESPONSES="/absolute/path/to/responses.json" python3 -m unittest discover -s tests
```

Without fresh answers, decision validation is explicitly skipped. These maintenance checks do not prove live deployment safety or performance gains.

## Install or update

Back up the existing installation, compare it with the source, then copy this Skill's files into `$CODEX_HOME/skills/agent-orchestrator` (normally `~/.codex/skills/agent-orchestrator`). Preserve unrelated local additions; do not use an indiscriminate delete-sync.

When upgrading from the former automatic-handoff version:

- Remove only Codex hook handlers that invoke this Skill's `scripts/session_hook.py`; preserve other hooks, their trust records and MCP servers.
- Remove the retired lifecycle reference, budget/session/continuation scripts and their dedicated tests/profile from the Skill installation. Preserve user customizations in a backup instead of silently replacing them.
- Remove previously adopted fixed context-budget overrides attributable to this Skill, preserving unrelated model/provider settings.
- Existing chats may have loaded the old instructions. Notify them only when the user authorizes it; continue existing work in place, without creating replacement chats or replaying completed actions.
- Project history can be cleaned when the user requests it and no active execution depends on it. Keep project indexes, user files and needed runtime/recovery inputs.

This version registers no hooks and recommends no context-window override. Let the host manage compaction. To roll back, restore only the files/configuration changed by the update; do not overwrite newer user edits.

## Use

```text
$agent-orchestrator
Implement <outcome>, preserving <constraints> and verifying <acceptance criteria>.
Delegate only where independent work or scoped context helps; continue in this chat.
```

A task's progress mechanism is chosen by the host/user/project, not this Skill. Keep one current record when needed, reuse valid results after compaction, and use a manual handoff or another main chat only on explicit user request. Commit, push, deployment and retry authority remain separate from delegation.

## Supporting resources

- [Execution boundaries](references/execution-boundaries.md): package ownership, actual decision points and scoped results.
- [Check evidence](references/check-evidence.md): proportional evidence, stopping rules and optional `scripts/candidate_check.py` usage.
- `tests/`: candidate-check regressions and independent decision scenarios.

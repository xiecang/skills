# agent-orchestrator

A Codex Skill for scoped multi-model work, independent review, evidence reuse, and resumable handoff. Execution rules are in [SKILL.md](SKILL.md); commands and recovery are in [session-lifecycle.md](references/session-lifecycle.md). Responses follow the user's language.

## Requirements

- Local Codex on macOS or Linux, Python 3.9+, and supported/trusted command hooks.
- Alibaba `open-code-review-delegate` and the `ocr delegate` CLI. No separate OCR model configuration is needed. Additional review Skills are optional, used only when explicitly requested.
- For automatic continuation, a client with `create_thread` and access to the same saved local project. Pure CLI use does not gain these client tools from this Skill.

Default roles and concurrency limits have one authoritative definition in [the Skill](SKILL.md#roles-and-authority). Review scope, frozen candidates, incremental rechecks, and required final checks also live there. Handoff creation and takeover are distinct; automatic continuation always requires valid original user authority.

## Validate the source

From this directory:

```bash
python3 tests/test_session_hook.py
```

The runtime and tests use Python's standard library. All test state is temporary. Run supported Python versions when changing script behavior. Discussing or maintaining this Skill does not register a business session or modify another project's state.

## Install and verify hooks

Use the current verified source directory, not an old ZIP. Back up an existing installation before replacing it. From this directory, copy the complete Skill:

```bash
task_skill_dir="${CODEX_HOME:-$HOME/.codex}/skills/agent-orchestrator"
mkdir -p "$task_skill_dir"
rsync -a --exclude='__pycache__' SKILL.md README.md agent-orchestrator.config.toml scripts references tests "$task_skill_dir/"
python3 "$task_skill_dir/tests/test_session_hook.py"
python3 "$task_skill_dir/scripts/session_hook.py" config
```

For upgrades from the former layout, remove the obsolete `首次接入.md` from the backed-up installation; this README replaces it. Do not delete other installed files indiscriminately.

The last command only prints configuration. Add this Skill's handlers once to Codex configuration, or update its existing handlers. Keep `PostToolUse` and `SessionStart` for `compact|resume`; remove only this Skill's obsolete `PreCompact` handler. Preserve unrelated hooks and entries in shared groups. Check that hooks are enabled and review/trust the current definitions in Codex `/hooks`; do not edit trust storage. See the [official hooks guide](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

A document-only update does not require registering hooks again. Script updates require checking that the active definitions remain enabled and trusted. Do not claim trust from an `active` session marker.

## Use

Add the project to the desktop App, start a local chat from that project, and select the coordinator model/effort specified by the Skill or your explicit override. For example:

```text
$agent-orchestrator
Implement: <task and acceptance criteria>.
Use the Skill's role defaults. Review, fix, verify, and commit accepted subtasks.
When handoff is needed, you may create a new main chat to continue this same task.
```

Request plan-only, no-commit, or manual continuation when desired. Existing verified authorization is reused; local preference evidence in the lifecycle reference belongs only to that user and is not authorization for new users.

Inspect registered state without modifying it:

```bash
python3 "$task_skill_dir/scripts/session_hook.py" status --root "/absolute/project/path"
```

`active` identifies the owner; `ready` means released and awaiting creation/reconciliation; `inactive` means the workflow ended; `unregistered` means no marker exists. State tracking does not stop actual writers. To stop, instruct the coordinator to preserve progress, stop writers, and leave the workflow.

## Optional configuration

`agent-orchestrator.config.toml` is an optional CLI profile, not a hook installer or automatic Skill invocation. Copy it to `$CODEX_HOME/agent-orchestrator.config.toml` (default `~/.codex/agent-orchestrator.config.toml`) and select it with `codex --profile agent-orchestrator` if wanted. Installation alone does not load it.

Verify the effective runtime window and this chat's loaded `total` compaction limit before registering a budget. Configured maxima, API capacity, and another process's settings are not proof of this chat's capacity. Overrides may be inherited by other models or subagents; recheck their limits rather than assuming the coordinator's window applies. Formula, examples, and startup-loop protection are defined in [Budget](references/session-lifecycle.md#budget).

## Files and maintenance

| File | Purpose |
| --- | --- |
| `SKILL.md` | Roles, investigation, scheduling, evidence, and review rules. |
| `references/session-lifecycle.md` | Authority, budget, state commands, continuation, archive, and recovery. |
| `scripts/session_hook.py` | Hooks and locked, atomic session state operations. |
| `scripts/create_thread_request.py` | Complete coordinator request JSON; no chat creation or state mutation. |
| `tests/test_session_hook.py` | Temporary-directory regression tests. |
| `agent-orchestrator.config.toml` | Optional model/window profile. |

Before deployment, compare source and installed files and preserve the current baseline, including uncommitted user changes. For rollback, restore only the intended files; first resolve active handoffs and startup-budget guards as described in [Compatibility](references/session-lifecycle.md#compatibility-and-rollback). Do not overwrite state with an older snapshot or remove creation records.

Compaction remains a fallback. The coordinator performs writer verification, archiving, and client operations; hooks cannot guarantee these. Logs and client capabilities can change. Script tests do not prove native cross-chat operation, and shorter instructions or cheaper models do not by themselves prove lower subscription usage.

# agent-orchestrator

A Codex Skill for scoped multi-model work, risk-based review, evidence reuse, and resumable handoff. Execution rules are in [SKILL.md](SKILL.md); commands and recovery are in [session-lifecycle.md](references/session-lifecycle.md). Responses follow the user's language.

## Requirements

- Local Codex on macOS or Linux, Python 3.9+, and supported/trusted command hooks.
- Follow user/project review-tool requirements. Alibaba `open-code-review-delegate` is optional otherwise, useful for code scope/rules in Git; runtime reads and non-Git delivery bookkeeping need no OCR.
- For automatic continuation, a client with `create_thread` and access to the same saved local project. Pure CLI use does not gain these client tools from this Skill.

Execution policy has one entrypoint: [SKILL.md](SKILL.md). It routes to [execution boundaries](references/execution-boundaries.md) for useful delegation and real decision points, [check evidence](references/check-evidence.md) for proportionate evidence and optional snapshot tooling, and [session lifecycle](references/session-lifecycle.md) for long-task handoff. This README covers setup and maintenance.

## Validate the source

From this directory:

```bash
python3 -m unittest discover -s tests
```

The runtime and tests use Python's standard library. All test state is temporary. Run supported Python versions when changing script behavior. Discussing or maintaining this Skill does not register a business session or modify another project's state.

Role behavior cases are in `tests/role_scenarios.json`; [forward-test instructions](tests/role_forward_test.md) define the independent exercise and response format without its expected decisions. The evaluator reads the current Skill and scenarios, returns action ownership/checkpoint decisions to a temporary JSON file, and binds its answers to the current policy/scenario SHA-256. Grade fresh answers with:

```bash
ORCHESTRATOR_ROLE_RESPONSES="/absolute/path/to/fresh-role-responses.json" python3 -m unittest discover -s tests
```

Without fresh responses, the role behavior suite is explicitly skipped; runtime unit tests alone do not establish role behavior. The grader checks decisions, scheduling and execution/evidence ownership rather than matching instruction wording. The workdir/receipt tests also run real commands in isolated temporary Git worktrees. Forward-testing is a maintenance check, not an extra gate on ordinary user tasks.

## Install and verify hooks

Use the current verified source directory, not an old ZIP. Back up an existing installation before replacing it. From this directory, copy the complete Skill:

```bash
task_skill_dir="${CODEX_HOME:-$HOME/.codex}/skills/agent-orchestrator"
mkdir -p "$task_skill_dir"
rsync -a --exclude='__pycache__' SKILL.md README.md agent-orchestrator.config.toml scripts references tests "$task_skill_dir/"
python3 -m unittest discover -s "$task_skill_dir/tests"
python3 "$task_skill_dir/scripts/session_hook.py" config
```

For upgrades from the former layout, remove the obsolete `首次接入.md` from the backed-up installation; this README replaces it. Do not delete other installed files indiscriminately.

The last command only prints configuration. Add this Skill's handlers once to Codex configuration, or update its existing handlers: `PostToolUse`, `SessionStart` for `startup|compact|resume`, `UserPromptSubmit`, and observational `PreCompact`. Replace only this Skill's obsolete handler; the new observer does not block compaction. Preserve unrelated hooks and entries in shared groups. Check that hooks are enabled and review/trust the current definitions in Codex `/hooks`; do not edit trust storage. See the [official hooks guide](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

A document-only update does not require registering hooks again. Script updates require checking that the active definitions remain enabled and trusted. Do not claim trust from an `active` session marker.

## Use

Start in the project and use the role defaults or an explicit model/effort override. Direct work is allowed when delegation adds no benefit; small tasks need no session registration. For long tasks using automatic continuation, add the project to the desktop App and start a local chat there. For example:

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

Configured maxima and API usage counters do not prove this chat's remaining context. [Budget](references/session-lifecycle.md#budget) defines native telemetry, thresholds and creation-loop protection. Missing/stale samples produce one advisory per episode; ordinary authorized work continues without polling. Automatic continuation still needs verified capacity, and confirmed handoff/ownership restrictions still apply.

## Files and maintenance

| File | Purpose |
| --- | --- |
| `SKILL.md` | Roles, investigation, scheduling, evidence, and review rules. |
| `references/session-lifecycle.md` | Authority, budget, state commands, continuation, archive, and recovery. |
| `references/execution-boundaries.md` | Execution ownership, coordinator verification, checkpoints and bounded reports. |
| `references/check-evidence.md` | Workdir/candidate-bound checks, receipts and one current evidence entry. |
| `scripts/candidate_check.py` | Capture inputs, run an authorized check and verify its bound receipt. |
| `scripts/session_hook.py` | Hooks and locked, atomic session state operations. |
| `scripts/context_budget.py` | Read-only native context accounting and freshness checks. |
| `scripts/create_thread_request.py` | Complete coordinator request JSON; no chat creation or state mutation. |
| `tests/` | State/native accounting regression tests and independent role behavior scenarios/grading. |
| `agent-orchestrator.config.toml` | Optional model/window profile. |

Before deployment, compare source and installed files and preserve the current baseline, including uncommitted user changes. For rollback, restore only the intended files; first resolve active handoffs and startup-budget guards as described in [Compatibility](references/session-lifecycle.md#compatibility-and-rollback). Do not overwrite state with an older snapshot or remove creation records.

Script/scenario tests do not prove native cross-chat operation or lower subscription usage. The Skill cannot enlarge model capacity or guarantee no compaction.

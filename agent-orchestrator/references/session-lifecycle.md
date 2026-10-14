# Main-session lifecycle

Only the coordinator executes this procedure. `<SKILL_DIR>` is the installed Skill directory; `<ROOT>` is the main workspace's project root. Use absolute paths. Subagents do not register or maintain main-session files.

Read by stage: [Authorization](#authorization), [Start](#start), and [Budget](#budget) at startup; [Prepare](#prepare) and [Create](#create-a-continuation) before handoff; [Reconcile](#reconcile) for `ready` recovery; [Take over](#take-over) and [Archive](#archive) in the successor. Consult [Hooks](#hooks) when checking setup/trust and [Compatibility](#compatibility-and-rollback) only for legacy state or rollback.

Commands use `CODEX_THREAD_ID`. If absent, add `--session "<verified actual caller ID>"` to mutations; a successor must not impersonate the old owner. `status` and `config` do not require an ID.

## Authorization

Verify original user authorization, task scope, and latest restrictions before automatic continuation. If the original context is missing, use `read_thread` on its source; an agent-written summary or state boolean is not authorization. Carry the verified evidence into the successor. Unverifiable authority means manual handoff, not broader permission.

Local preference for this installation's user, recorded on 2026-10-11 in chat `01a12963-7c28-7180-aaaa-f979067a8ca0`:

> 这个是否可以在 skill 中自动做，我希望能做到不压缩，自动交接，自动新聊天接续

The user subsequently confirmed:

> 我同意你这个流程

This authorizes early handoff and a new chat continuing the same task, with compaction as fallback. Reuse that authorization for this user's Skill tasks; an explicit manual-mode or stop request overrides it. It grants no authority to other users receiving the Skill. Preserve the Chinese originals when citing this evidence.

## Start

Resolve roles from [SKILL.md](../SKILL.md#roles-and-authority), verify tool/model availability and hook trust, and record original overrides. Check the current plan belongs to this task and no unreleased coordinator exists. Record scope, role choices, actual session ID, authorization/source, workspace, Git baseline, and existing changes.

The chat must start inside `<ROOT>`; setting a shell command's `workdir` does not change the chat's startup directory. Continuations need the same main workspace. Register:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" activate --root "<ROOT>"
```

New tasks default to `auto_continue = true`; add `--manual-continue` for explicit manual mode or missing authority. Existing-owner retries and takeovers inherit the current choice unless `--manual-continue` or `--auto-continue` explicitly overrides it. The default is a workflow preference, not permission.

The script writes only `.codegraph/agent-orchestrator.json` and its lock. State v2 phases are `active`, `ready`, and `inactive`. It does not write plans, business code, indexes, or global configuration, and cannot stop writers for you.

Before dispatch or business writes, run `check-budget` with this chat's verified model and rollout path, then inspect `status` for `startup_budget_checked` and `budget_evidence`. This also applies when an existing chat is reactivated after planning; its history remains in context. A small-output tool may be needed to produce the first native sample.

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" check-budget --root "<ROOT>" --model "<ACTUAL_MODEL>" --transcript-path "<ACTUAL_ROLLOUT_PATH>"
```

## Budget

Use the native runtime's **active-context accounting**, not `last_token_usage.total_tokens` or cumulative API usage. The hook reads the matching chat's `post sampling token usage` sample from `$CODEX_HOME/logs_2.sqlite` in read-only mode, locating it beside the rollout's `sessions` directory. The sample must match the actual model and current turn, follow the latest turn/compaction epoch, and remain current relative to the rollout's latest usage record.

For supported `Total` scope, `U = total_usage_tokens = auto_compact_scope_tokens`, `W = full_context_window_limit`, and `C = auto_compact_scope_limit`. These are loaded runtime values; configuration files alone do not prove them. State `budget_evidence` records the counters, window, limit, database path and row ID. `api_tokens` is diagnostic only.

```text
W = runtime effective context window
C = native loaded total compaction limit for this session and model
B = min(W, C, any matching manually verified lower cap)
R = max(ceil(B / 5), 2 * (35,000 + 15,000))
T = B - R; request handoff when U >= T
```

The 35K handoff cost and 15K request growth are conservative historical estimates; 20% is a policy reserve, not a proven optimum. Round upward. With native `W=828,400` and `C=780,000`, reserve 156,000 and hand off at 624,000 **native context tokens**. There is no fixed 200K or 319K cap.

Native telemetry supplies C automatically. Optional flags on startup or takeover `activate` can record a separately verified lower cap; they never expand the native budget:

```bash
--compact-limit <VERIFIED_LIMIT> --compact-model <ACTUAL_MODEL>
```

These flags record evidence, not settings changes. Check `status` for `compaction_budget`. Another process's config, API capacity, another model's history, or `body_after_prefix` does not verify this chat's budget. Owner retries retain the lower cap; successors verify their own runtime budget.

Missing, stale, mismatched or incompatible native telemetry yields `budget_evidence.verified = false`. Stop new dispatch, reduce output, attempt a small-output budget check, and report the limitation if it remains unavailable. API counts cannot substitute for native accounting; no guessed threshold or automatic creation is allowed. `BodyAfterPrefix` currently requires manual verification rather than silently mixing counting scopes. If `R >= B`, set `handoff_budget_blocked`, preserve work, and report insufficient capacity.

Every new activation, reactivation and takeover starts with `startup_budget_checked = false`; owner retries preserve the check. A positive, verified native sample completes it. Initial/reactivated chats use the normal threshold so long existing history can be handed off. For a successor, `T - U <= 15,000` instead blocks automatic continuation, preventing a startup loop. Zero/unknown counts do not complete the check.

A blocked session stays blocked across repeated tools and recovery until valid positive usage shows `R < B` and `U + 15,000 < T`, after a larger budget or smaller context. Unknown/zero counts cannot clear it. A compact event before startup verification must check the same budget before requesting handoff; missing evidence defers that request. `begin-continuation` cannot grant creation while blocked or unchecked. Existing `ready` handoffs remain read-only; do not reset state to evade the guard. A user-authorized manual resolution remains possible after independently checking capacity and stopped writers.

Budget updates use the existing lock. A pending handoff is not revoked by a later budget check; once budget-blocked, a handoff request cannot bypass that state. Ordinary compaction still initiates recovery handoff when no guard applies. This is a fallback policy, not a guarantee against earlier compaction.

Verified incident, 2026-10-14: this installation's native row `6289369` recorded `U=780,878`, `C=780,000`, `W=828,400`, `Total`, and `token_limit_reached=true`. The same chat's rollout line 1907 reported API `last_token_usage=419,131`. Compaction followed the native 780K limit; 419K was a different counter, not an early compaction threshold. Regression fixtures retain these accounting fields, without treating this incident as a universal budget.

## Prepare

1. Stop dispatch. Have every active agent preserve results and stop writing; verify each writer. Unknown activity prevents release.
2. Check the current plan, Git state, and evidence. Before replacing a received Handoff, ensure it has been [archived](#archive). Write one complete `.codegraph/HANDOFF.md`: objective/acceptance, authority/constraints, role choices, old owner ID, workspaces/baselines/commits, user and task changes, valid findings/gaps, check results, unfinished work, writer status, next actions, and absolute evidence paths.
3. Once complete and ready to leave business execution, run:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" prepare-handoff --root "<ROOT>" --writers-stopped
```

The flag asserts a verified fact; the script cannot inspect agents. It hashes the nonempty Handoff, creates a unique `handoff_id`, and enters `ready` with creation `not_started`. Save its returned ID rather than inventing one. A retry checks the same digest and preserves the ID and creation history.

From `ready`, the old owner only handles creation, reconciliation, and reporting: no business/plan/Handoff writes, dispatch, or `deactivate`. Recovery resumes reconciliation without regenerating the document.

## Create a continuation

Manual mode skips automatic creation. Otherwise verify [authority](#authorization), use `list_projects` to identify the local project starting in the same `<ROOT>`, and resolve the coordinator from the Skill role table. Do not replace this with a projectless directory, full-history fork, or `handoff_thread`. If the required capability/workspace/model cannot be verified, keep a manual handoff.

Save a prompt containing the following to `<PROMPT_FILE>`:

```text
Use $agent-orchestrator to continue the same authorized task.
Original user authority: <verbatim instruction and source chat>; latest restrictions: <facts>.
Main workspace: <ROOT>; previous owner: <OLD_SESSION_ID>; handoff ID: <HANDOFF_ID>.
Resolved coordinator: <MODEL> / <EFFORT>; basis: <verified user override or Skill default>.
The create request passes these as top-level model and thinking. Verify the actual runtime values.
Read the current plan, HANDOFF.md, and session state. Verify authority, startup directory, Git state,
and that the old scheduler and all writers stopped. Preserve the ready handoff_id, handoff_sha256,
and their read-result location before takeover; the new active state omits the old digest.
Follow “Take over” in references/session-lifecycle.md, including this session's budget verification.
After successful takeover, archive the received snapshot before updating the current plan.
Reuse valid evidence and continue only unfinished work. Report failures without clearing ownership.
```

Generate the complete request; `--model` and `--thinking` are required and must contain the resolved values:

```bash
python3 "<SKILL_DIR>/scripts/create_thread_request.py" --project-id "<PROJECT_ID>" --prompt-file "<PROMPT_FILE>" --model "<MODEL>" --thinking "<EFFORT>" --title "<TITLE>"
```

The helper only prints JSON. Verify top-level `model`, `thinking`, local target, and prompt. Tool availability is the authority on supported values; `thinking` is not the subagent field `reasoning_effort`. Use the entire generated object, not a hand-rebuilt request that drops model arguments.

Prepare the request before acquiring a creation permit:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" begin-continuation --root "<ROOT>" --handoff-id "<HANDOFF_ID>"
```

Call `create_thread` once only if **this invocation** returns `create_allowed = true`. The lock persists `creating` first; repeats cannot reuse permission. An uncertain permit result or a crash before creation also requires reconciliation, not a retry.

After a real `threadId` is returned, record it and display the created-chat reference as required by the client:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" record-continuation --root "<ROOT>" --handoff-id "<HANDOFF_ID>" --result created --thread-id "<NEW_THREAD_ID>"
```

Use `--result failed` for a definite failure or `--result unknown` for timeout/uncertainty, without `--thread-id`. A queued `clientThreadId` is not a takeover ID. Keep sensitive error content out of state. No attempted stage receives another automatic creation permit.

## Take over

Before any business write, verify original authority, actual model/effort, startup workspace, Git inputs, Handoff digest, and stopped old writers. A requested model is not proof of the runtime model. Preserve the ready digest before activation; it is required for archiving. If any check fails, preserve the chat/state and report; do not create another chat or silently substitute a model.

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" activate --root "<ROOT>" --resume-from "<OLD_SESSION_ID>" --handoff-id "<HANDOFF_ID>"
```

Append verified [budget flags](#budget), or omit them and report C unverified. The lock validates the ready owner, ID, document digest, and recorded successor when present. Only one successor wins; retrying the same successful takeover preserves its settings and startup check. Only successful activation permits writing. Archive next, update the current plan, and honor startup-budget reminders before dispatching business work.

## Reconcile

A successful creation is not completed handoff. The old owner checks, in order:

1. `status`: matching new owner, `resumed_from`, and `accepted_handoff_id` prove takeover. The successor may already have advanced beyond `active`.
2. If not taken over and a real ID is known, `read_thread` verifies workspace/prompt; runtime metadata or the new chat's own runtime evidence verifies model/effort. Prefer bounded `wait_threads` updates over repeated full reads.
3. If the ID is missing, inspect candidate chats and verify handoff ID, previous owner, workspace, and original prompt. Similar titles or an absent list result prove nothing. Record only a uniquely verified candidate.
4. Reconcile for at most 60 seconds. If uncertain, preserve `creating`/`unknown` or the known receipt, report the Handoff path, IDs, and blocker, and pause automatic handling. Never create a duplicate.

A late receipt after takeover verifies the accepted ID and successor and returns current state unchanged, including a successor's later handoff. The old chat ends only after confirming takeover; otherwise report “created; takeover unconfirmed.” Existing wrong-model chats require authorized, supported client operations to switch. Skill changes do not switch running chats.

## Archive

Only the new active owner archives, after successful takeover and before updating the current plan. This is a coordinator file operation, not a new script command or takeover condition. Old owners and `ready` sessions remain read-only.

1. Confirm current ownership and matching `resumed_from` / `accepted_handoff_id`. Use `.codegraph/handoffs/<accepted_handoff_id>.md`, never a generated or next-handoff ID. Use the pre-takeover `handoff_sha256`; after recovery, retrieve that read result. If unavailable, report archive failure.
2. Copy the verified `HANDOFF.md` byte-for-byte, without headers or edits; verify source/archive SHA-256 against that digest. Create without overwriting an existing target. Reject symlink archive directories/files rather than following them.
3. Same ID and identical content is an idempotent success. Different content, partial copies, or failed verification preserve both the archive and current Handoff and require reporting; do not overwrite, delete, or rename around the conflict.
4. Keep only the latest archive link and useful conclusions in the current plan. Historical archives are immutable, loaded only for a specific need, and never automatically deleted. Keep the source Handoff until the current owner prepares the next complete snapshot.

Archive failure does not undo takeover or add a business-write gate. Preserve the original snapshot, record/report the failure in the plan, and resolve it before overwriting the Handoff for another handoff. Retries still require active ownership; `ready` recovery only reconciles.

## Finish

On completion, cancellation, or leaving this workflow, verify all agents stopped writing, update the current plan, then run:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" deactivate --root "<ROOT>"
```

Waiting for a user or closing the app is not completion. Do not deactivate automatically on `SessionEnd`. A released old owner cannot cancel a `ready` handoff; a verified successor must take ownership first, confirm no writers, and deactivate without resuming cancelled business work.

## Hooks

Run `session_hook.py config` to print definitions; installation and trust steps are in [README](../README.md#install-and-verify-hooks).

| Event | Matcher | Purpose |
| --- | --- | --- |
| `PostToolUse` | All tools | Check native budget and remind about unfinished handoff. |
| `SessionStart` | `^(startup\|compact\|resume)$` | Check startup/resume budget; compact starts fallback recovery when no guard applies. |
| `UserPromptSubmit` | All prompts | Recheck budget when the user continues an existing chat. |
| `PreCompact` | `^(auto\|manual)$` | Report both counters and actual limit; observe without blocking or mutating ownership. |

Current [official hooks](https://learn.chatgpt.com/docs/hooks#precompact) support `PreCompact` with `continue: false`, which stops the turn before compaction. This Skill emits only observational `systemMessage`: blocking would also prevent the coordinator's next model request, and hooks cannot create the continuation themselves. Enable a blocker only after verifying an authorized recovery path in that client; keep post-compaction recovery. Replace only this Skill's obsolete handler, preserving unrelated hooks and shared groups. Register each handler once and trust its current definition through the client; never edit trust storage directly.

The transcript's initial `session_meta.id` must match the actual session. This excludes subagents that share the parent's event ID/cwd. Ordinary chats are silent; a previous owner only receives a stop-writing reminder. Recovery normally reads identity only, except when startup or blocked-budget recovery requires usage verification.

Missing/unverifiable logs do not trigger guessed handoffs. Rollout and native database formats are not stable APIs; revalidate them on client upgrades. Recovery normally checks identity only; ordinary budget checks scan rollout metadata and query one native sample. Hooks cannot wake stopped agents or guarantee recovery when trust, client capability, logs, or service behavior differs. [Input contract](https://learn.chatgpt.com/docs/hooks#common-input-fields).

## Compatibility and rollback

Reading v1 never rewrites it. Authorized owner mutations upgrade it to v2. Legacy `ready` must be upgraded by the old legitimate owner with `prepare-handoff --writers-stopped`; it keeps the digest and gets creation `unknown`, not a fresh creation permit. Reconcile before recording a known successor or continuing manually. If the old chat is unavailable, independently verify stopped writers before any necessary operation with the verified old ID.

`startup_budget_checked` is an optional v2 boolean. Missing means an older active session. Reads preserve it; new activation/reactivation/takeover initializes it, owner retries preserve it. `budget_evidence` is optional; an explicitly unverified record blocks creation even after an earlier successful startup check. Invalid state types fail without rewriting.

Before updating, back up source, installation, and any configuration being changed. Complete or independently verify stopped in-flight handoffs before reverting scripts. Older code may not honor newer guards: preserve state and Handoff snapshots, and resolve blocked/unchecked sessions before rollback. Never clear creation history or ownership to bypass errors. Script tests and document checks do not establish native end-to-end continuation.

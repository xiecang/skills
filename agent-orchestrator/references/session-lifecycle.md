# Main-session lifecycle

Use this procedure for long tasks needing automatic continuation or an existing registered handoff. Small direct tasks need no session registration. Only the coordinator manages session ownership; `<SKILL_DIR>` is the installed Skill directory and `<ROOT>` the main workspace root. Use absolute paths.

Read by stage: [Authorization](#authorization), [Start](#start), and [Budget](#budget) at startup; [Prepare](#prepare) and [Create](#create-a-continuation) before handoff; [Reconcile](#reconcile) for `ready` recovery; [Take over](#take-over) and [Archive](#archive) in the successor. Consult [Hooks](#hooks) when checking setup/trust and [Compatibility](#compatibility-and-rollback) only for legacy state or rollback.

Commands use `CODEX_THREAD_ID`. If absent, add `--session "<verified actual caller ID>"` to mutations; a successor must not impersonate the old owner. `status` and `config` do not require an ID.

## Authorization

Verify original user authorization, task scope, and latest restrictions before automatic continuation. Carry the original excerpts and source locations into the successor, which checks the needed original evidence and any newer restrictions without replaying intervening chat histories. If original evidence is missing, use `read_thread` on its source; an agent-written summary or state boolean is not authorization. Unverifiable authority means manual handoff, not broader permission.

Local preference for this installation's user, recorded on 2026-10-11 in chat `01a12963-7c28-7180-aaaa-f979067a8ca0`:

> 这个是否可以在 skill 中自动做，我希望能做到不压缩，自动交接，自动新聊天接续

The user subsequently confirmed:

> 我同意你这个流程

This authorizes early handoff and a new chat continuing the same task, with compaction as fallback. Reuse that authorization for this user's Skill tasks; an explicit manual-mode or stop request overrides it. It grants no authority to other users receiving the Skill. Preserve the Chinese originals when citing this evidence.

## Start

Resolve roles from [SKILL.md](../SKILL.md#choose-execution-ownership), verify tool/model availability and hook trust once, and record original overrides. Reuse the task entry for scope, session/authority source, workspace, Git baseline and existing changes; do not create duplicate registration evidence.

If another task owns the root marker, do not overwrite it or wait merely for a plan-directory release. Use a task-specific plan in permitted scratch space and continue independent authorized work after checking actual file/resource conflicts. Without an available registered workspace, native compaction/manual handoff is the fallback; automatic continuation through this hook is unavailable. Routine plan placement needs no user exception approval. Do not move an active ready handoff or evade its ownership rules.

The chat must start inside `<ROOT>`; setting a shell command's `workdir` does not change the chat's startup directory. Continuations need the same main workspace. Register:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" activate --root "<ROOT>"
```

New tasks default to `auto_continue = true`; add `--manual-continue` for explicit manual mode or missing authority. Existing-owner retries and takeovers inherit the current choice unless `--manual-continue` or `--auto-continue` explicitly overrides it. The default is a workflow preference, not permission.

The script writes only `.codegraph/agent-orchestrator.json` and its lock. State v2 phases are `active`, `ready`, and `inactive`. It does not write plans, business code, indexes, or global configuration, and cannot stop writers for you.

The trusted hook normally records native budget automatically. At registration/reactivation, inspect available budget evidence once; use `check-budget` only if that evidence is unavailable or a handoff decision needs it. Unknown telemetry does not block ordinary authorized execution, and producing a fresh sample is not a separate work package. Automatic continuation creation still requires positive verified capacity; history is not proof of current capacity.

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" check-budget --root "<ROOT>" --model "<ACTUAL_MODEL>" --transcript-path "<ACTUAL_ROLLOUT_PATH>"
```

## Budget

Budget is a scheduling signal, separate from user authority and project acceptance. A missing/stale native sample must not suspend ordinary work, trigger evidence repair, or cause manual polling. The hook records diagnostics and reports an unavailable-telemetry episode once, then remains quiet until recovery. Preserve progress and allow native compaction/manual handoff if telemetry stays unavailable; never label unknown capacity as verified.

The hook reads the matching owner's/model's/current-turn `post sampling token usage` from the read-only native log database beside the rollout. It checks epoch and freshness against current usage. Do not replace this with API request/cumulative counts or loosen accounting checks to manufacture a result. Local log formats are not stable interfaces; revalidate on client upgrades.

For supported `Total` scope:

```text
U = native total_usage_tokens = auto_compact_scope_tokens
W = native full_context_window_limit
C = native auto_compact_scope_limit
B = min(W, C, any matching manually verified lower cap)
R = max(ceil(B / 5), 2 * (35,000 + 15,000))
T = B - R
```

The reserve is a conservative policy, not a measured optimum. For W=828,400 and C=780,000, T=624,000 native context tokens. A verified U >= T requests handoff; preserve the request until resolved. Before a heavy check, use available capacity and observed growth to choose a useful checkpoint; let already-owned checks finish with bounded waits when possible. If interrupted, retain the actual result and unfinished scope, never a pass. Stop writers before ownership release.

`startup_budget_checked` records a positive verified native sample, not permission to execute business work. `budget_evidence.verified=false` and `last_verified` distinguish unknown current capacity from historical diagnostics. Neither missing/zero usage nor history grants automatic creation. New activations/takeovers reset the startup flag; successful same-owner retries preserve it.

`handoff_budget_blocked` protects against continuation loops when the reserve consumes capacity or a successor has <=15,000 tokens of margin. Keep the block until a positive sample shows R < B and U + 15,000 < T. `begin-continuation`/`retry-continuation` still reject blocked, unchecked or explicitly unverified budgets. Do not reset ready state or creation history to bypass these guards. A real capacity shortage calls for a smaller handoff or manual resolution, not repeated creation.

A verified lower cap can be recorded at activation with `--compact-limit <LIMIT> --compact-model <MODEL>`. These are evidence flags, not settings changes, and cannot enlarge native capacity. Ordinary compaction remains a fallback; neither telemetry nor this Skill guarantees zero compaction.

## Prepare

1. Stop dispatch. Have every active agent preserve results and stop writing; verify each writer. Unknown activity prevents release.
2. Persist the [current package state](check-evidence.md#handoff), archiving a received Handoff before replacement. Write `.codegraph/HANDOFF.md` as a short operational snapshot: objective and remaining acceptance, original authority source/latest limits, current owner/workspace/candidate, stopped writers, blockers and next executable action. Link necessary evidence; omit historical digest inventories, repeated policy and completed investigations. Aim for a page of current state, adding only indispensable safety details. Reuse these entries rather than authoring a second report.
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
Verify actual model/effort against the resolved coordinator, whether the request used explicit
overrides or verified matching client defaults. Read the current plan, HANDOFF.md and session state.
Follow “Take over” and “Archive” in references/session-lifecycle.md, including authority, workspace,
stopped-writer and startup-budget verification. Preserve the ready handoff_id, handoff_sha256 and
their read-result location before activation; the new active state omits the old digest.
Assign only unfinished execution using references/execution-boundaries.md and valid package evidence.
Report failures without clearing ownership or rewriting received history.
```

Generate the complete request; `--model` and `--thinking` are required and must contain the resolved values:

```bash
python3 "<SKILL_DIR>/scripts/create_thread_request.py" --project-id "<PROJECT_ID>" --prompt-file "<PROMPT_FILE>" --model "<MODEL>" --thinking "<EFFORT>" --title "<TITLE>"
```

The helper only prints JSON. Verify top-level `model`, `thinking`, local target, and prompt against the actual tool's constraints; `thinking` is not the subagent field `reasoning_effort`. Tool constraints take precedence over this helper. If overrides are permitted only for a specific human model choice, do not treat the Skill's defaults as that choice. When the actual configured client model AND effort are independently verified to match the resolved coordinator, use `--use-verified-client-defaults` to omit both overrides and include the expected runtime in the prompt. Otherwise preserve a manual handoff until the mismatch is resolved; no guessed defaults, silent effort reduction or model substitution. The successor must still verify its actual model/effort before takeover/business execution. Use the entire generated request.

Prepare the request before acquiring a creation permit:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" begin-continuation --root "<ROOT>" --handoff-id "<HANDOFF_ID>"
```

Call `create_thread` once only if **this invocation** returns `create_allowed = true`. The lock persists `creating` first; repeats cannot reuse permission. An uncertain permit result or a crash before creation also requires reconciliation, not a retry.

Save the permit's `continuation.attempt_id`. After a real `threadId` is returned, record it and display the created-chat reference as required by the client:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" record-continuation --root "<ROOT>" --handoff-id "<HANDOFF_ID>" --attempt-id "<ATTEMPT_ID>" --result created --thread-id "<NEW_THREAD_ID>"
```

Use `--result failed` for a definite failure or `--result unknown` for timeout/uncertainty, without `--thread-id`, retaining the attempt ID. A queued `clientThreadId` is not a takeover ID. Keep sensitive error content out of state. Ordinary `begin-continuation` never reissues a permit after an attempt. Legacy first attempts may omit attempt IDs; retry receipts must match their new ID, so delayed old receipts cannot overwrite a new attempt.

### Definite preflight rejection

One additional creation attempt is allowed only when the original tool result proves rejection before any chat was created. A generic failure, timeout, missing list result, queued client ID, `creating` or any uncertainty does not qualify. Reconcile actual candidate chats first. An attempt ever recorded `unknown` remains ineligible for retry, even if later labelled `failed`; reconcile a known successor or use manual resolution.

Before retry, resolve the actual capability/parameter issue, verify unchanged original authority or a new human retry instruction and its scope, and confirm no successor exists. A new instruction alone does not prove non-creation or authorize changing models. Save a bounded durable evidence file with the raw definite rejection, authority source, corrected request/capability evidence and reconciliation results. Then run:

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" retry-continuation --root "<ROOT>" --handoff-id "<HANDOFF_ID>" --attempt-id "<FAILED_ATTEMPT_ID>" --preflight-rejected --no-successor --retry-evidence "<ABS_EVIDENCE_FILE>"
```

The flags assert coordinator-verified facts; the script cannot prove authority, discover chats or validate the client's model catalog. Under the same lock and ownership/digest/budget guards it preserves the failed attempt/evidence hash, issues a new attempt ID and grants at most one extra permit. Call `create_thread` only for that invocation's `create_allowed=true`, then record the result against the NEW attempt ID. A second failure stops automatic creation; preserve evidence for manual resolution. Never reset ready/creation state, change the Handoff digest or erase failure history to retry.

## Take over

Before any business write, verify original authority, actual model/effort, startup workspace, Git inputs, Handoff digest, and stopped old writers. A requested model is not proof of the runtime model. Preserve the ready digest before activation; it is required for archiving. If any check fails, preserve the chat/state and report; do not create another chat or silently substitute a model.

```bash
python3 "<SKILL_DIR>/scripts/session_hook.py" activate --root "<ROOT>" --resume-from "<OLD_SESSION_ID>" --handoff-id "<HANDOFF_ID>"
```

Append verified [budget flags](#budget), or omit them and obtain native evidence with `check-budget`. The lock validates the ready owner, ID, document digest, and recorded successor when present. Only one successor wins; retrying the same successful takeover preserves its settings and startup check. Only successful activation permits writing. Archive next and update the current plan. Assign only unfinished execution according to [Execution boundaries](execution-boundaries.md); inspect budget evidence once, without making telemetry recovery a business gate. Do not re-review accepted candidates merely because ownership changed.

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
| `PostToolUse` | All tools | Check native budget; emit a new handoff request or the first telemetry warning, not repeated reminders. |
| `SessionStart` | `^(startup\|compact\|resume)$` | Check startup/resume budget; compact starts fallback recovery when no guard applies. |
| `UserPromptSubmit` | All prompts | Recheck budget when the user continues an existing chat. |
| `PreCompact` | `^(auto\|manual)$` | Report both counters and actual limit; observe without blocking or mutating ownership. |

Current [official hooks](https://learn.chatgpt.com/docs/hooks#precompact) support `PreCompact` with `continue: false`, which stops the turn before compaction. This Skill emits only observational `systemMessage`: blocking would also prevent the coordinator's next model request, and hooks cannot create the continuation themselves. Enable a blocker only after verifying an authorized recovery path in that client; keep post-compaction recovery. Replace only this Skill's obsolete handler, preserving unrelated hooks and shared groups. Register each handler once and trust its current definition through the client; never edit trust storage directly.

The transcript's initial `session_meta.id` must match the actual session, excluding subagents that share the parent's event ID/cwd. Ordinary chats are silent; pending-handoff/previous-owner reminders appear on session recovery or new user input, not after every tool. Recovery normally reads identity only; startup or blocked-budget recovery also verifies usage. Budget checks scan rollout metadata and query one native sample.

Missing/unverifiable logs do not trigger guessed handoffs. Rollout/native database formats are not stable APIs; revalidate them on client upgrades. Hooks cannot wake stopped agents or guarantee recovery across differences in trust, capabilities, logs or service behavior. [Input contract](https://learn.chatgpt.com/docs/hooks#common-input-fields).

## Compatibility and rollback

Reading v1 never rewrites it. Authorized owner mutations upgrade it to v2. Legacy `ready` must be upgraded by the old legitimate owner with `prepare-handoff --writers-stopped`; it keeps the digest and gets creation `unknown`, not a fresh creation permit. Reconcile before recording a known successor or continuing manually. If the old chat is unavailable, independently verify stopped writers before any necessary operation with the verified old ID.

`startup_budget_checked` is an optional v2 boolean. Missing means an older active session. Reads preserve it; new activation/reactivation/takeover initializes it, owner retries preserve it. `budget_evidence` is optional; an explicitly unverified record blocks automatic creation even after an earlier successful startup check, but does not block ordinary authorized work. Invalid state types fail without rewriting.

Before updating, back up source, installation, and any configuration being changed. Complete or independently verify stopped in-flight handoffs before reverting scripts. Older code may not honor newer guards: preserve state and Handoff snapshots, and resolve blocked/unchecked sessions before rollback. Never clear creation history or ownership to bypass errors. Script tests and document checks do not establish native end-to-end continuation.

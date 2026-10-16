# Execution boundaries

Read when delegating a package or deciding an external action. [SKILL.md](../SKILL.md) owns role selection, scheduling and review policy.

## One owner through delivery

The coordinator owns scope, authority, dependencies and unresolved decisions. It can execute directly when delegation adds no useful independence or context isolation. An assigned worker owns the complete package through diagnosis, implementation, fixes, checks, builds, artifact preparation and authorized delivery/cleanup. Keep that owner across stages; do not add a separate integration, commit or release agent without actual work requiring it.

Dispatch the outcome, actual workspace/baseline, permitted files/actions, relevant contracts, valid findings, required checks and recovery constraints. Include the remaining sequence, not one message per shell command. Subagents do not delegate further or keep competing main plans. Explicit user model/role limits still apply.

If only the coordinator has a necessary authorized tool, it may perform that step and return the result to the execution owner. Record the reason in the existing entry; no user permission is needed merely for changing the executor. Lack of access in every available executor is a real blocker, not permission to bypass controls.

## Decision points, not approval-file ceremonies

An owner continues within existing authority after required checks pass. Pause only at a user/project/platform-required approval, an unresolved material risk, changed scope, conflicting evidence or an unmet dependency. Do not insert a coordinator signature between preparation, execution and observation just because they are different stages.

For an external change, establish the actual target/action, authority, accepted artifact/configuration, required checks and relevant recovery method. Run the platform's real gate where required. A local file saying "approved" adds no authority and must not be invented as an extra gate. If an existing runner enforces a required gate, preserve it; change such a contract only through an authorized implementation change, never bypass it during a live run.

Resolve tool permissions and bounded read-only connectivity before an attempt with side effects. Reuse the accepted runner and validate the current parameters/target. Runtime readback and required live acceptance remain necessary, but do not become new code-review packages. Preserve failed/unknown results; check current state before any authorized retry. User retry limits and platform approval rejections remain binding.

## Evidence and acceptance

Use [check evidence](check-evidence.md) to bind required checks to the actual inputs. Return a bounded result with the original command/workdir/exit/log, review findings if applicable, remaining gaps and next action. Keep detailed logs with the owner; summaries alone cannot establish a disputed result.

At a real acceptance boundary, inspect only what the decision still needs:

- Valid original authority and any newer limits.
- Actual candidate/artifact and relevant configuration, including user edits.
- Required checks on those inputs, with their actual results and exceptions.
- Applicable review and closure of confirmed findings.
- Required final/runtime checks and recovery/cleanup scope.

Reuse established evidence. Coordinator acceptance is a decision, not another full review or a newly hashed certificate. Missing or contradictory evidence returns to its owner for a targeted correction; do not reconstruct the entire investigation. A new index, log name or unchanged artifact copy does not invalidate source review. A changed target, configuration or behavior does require the checks that change affects.

## Recovery

After compaction or interruption, use the current task record and original authority source to continue only unfinished work in the same main chat. Reuse still-valid approvals within their exact conditions; do not reopen them because the chat changed. One component's exception does not cover another or a new risk. Preserve privacy limits and ask only for human-only actions, genuinely missing authority or decisions requiring the user.

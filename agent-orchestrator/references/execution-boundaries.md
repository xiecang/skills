# Execution boundaries

Read before dispatch, acceptance, capability exceptions or resumed execution. [SKILL.md](../SKILL.md) defines role/model selection, concurrency and review modes; this reference defines the handoff between execution and coordinator decisions.

## Ownership

Plan/session/handoff operations, bounded identity/status checks and acceptance/release decisions belong to the coordinator. Routine execution remains with its assigned owner across decision checkpoints.

An execution package includes its permitted diagnosis/reproduction, implementation, fixes, checks, integration, builds/scans, artifact preparation, commits and deployment/trial/rollback/cleanup. Acceptance of a source commit does not end an unfinished release package: retain the worker or explicitly assign a release worker.

Detailed vulnerability matching/applicability analysis belongs to the qualified expert/reviewer; the execution owner performs the approved fix or disposition. Verify existing accepted-risk conditions; new risk acceptance beyond current authority requires a user decision.

## Dispatch and checkpoints

Dispatch the package's current plan entry with its actual workspace/baseline, contracts, valid findings/gaps, user limits and recovery requirements. Include the entire permitted remaining sequence and explicit review/decision checkpoints. Delegation adds no authority to upgrade dependencies, waive gates, accept risk, push, deploy or delete.

Use explicit tool workdirs for commands. For acceptance checks/results, verify frozen inputs and receipts under [Check evidence](check-evidence.md); inspection and editing do not require a frozen candidate.

For release, the worker prepares the exact artifact, invokes the real safety gate, prepares backups and a cleanup allowlist, then pauses at the specified decision checkpoint with evidence indexes. The coordinator applies the checklist below before the worker performs the approved next step. Failed gates or missing authority block the affected action; permitted evidence preparation may continue.

## Verification and reports

Return a bounded summary of the decision-relevant fields in the [current package entry](check-evidence.md#keep-one-current-evidence-entry), with absolute evidence indexes. Raw logs, inventories and detailed analysis stay with the responsible agent/evidence files. The coordinator reads original sections needed for its decision; a “passed” summary alone is insufficient. Return missing, stale or contradictory evidence to its owner for correction rather than reconstructing the whole investigation.

At each required acceptance checkpoint, the coordinator verifies:

- Original user authority, current limits and the exact target/action to authorize.
- Complete task-diff and artifact identities, including dirty/untracked inputs and relevant configuration.
- Required commands actually ran on those inputs; success, failures and exceptions match the original logs and current candidate.
- The applicable review covers the scope and confirmed findings are closed; any required risk acceptance is authorized. Pending risk acceptance blocks the affected action.
- Mandatory integration/final-state gates and, for external changes, backups/rollback and exact cleanup scope are satisfied.

Establish these facts through existing verifiers and targeted source/diff/log inspection, then apply the [stopping rule](check-evidence.md#accept-and-reuse). Coordinator acceptance does not add another full review or reproduce the worker's checks.

## Capability gaps and handoff

Resolve an unavailable worker capability with another authorized executor or supported tool. If none can perform the step, mark that step blocked and preserve evidence; do not silently move an entire package into the main chat. An explicit user instruction or a genuinely coordinator-only operation can justify a narrow direct execution exception. Record why, the exact scope and unchanged acceptance/security checks; return subsequent execution to the worker. This exception grants no additional authority or model substitution.

Record conditional model fallbacks, gate exceptions and privacy limits with the original user source, scope/conditions and current status. Reuse valid approvals across handoffs and fixes within that scope; an exception for one component does not cover another or new risks. Capacity failures do not authorize model substitution. Reconcile pending decisions against later human replies instead of trusting stale Handoff labels.

Within existing authority, use available diagnostics to reproduce confirmed symptoms, protecting private content and unsaved data. Ask the user only for human-only steps, unresolved data risk or new scope/product decisions requiring approval; established symptoms do not need repeated confirmation.

After [takeover](session-lifecycle.md#take-over), assign the unfinished sequence using the verified package entry and its valid evidence; continue from the recorded checkpoint rather than replaying completed stages.

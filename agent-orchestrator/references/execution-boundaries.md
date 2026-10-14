# Execution boundaries

Apply this reference when dispatching a work package, accepting its result, resolving a capability gap, or resuming after handoff. Model/effort choices, concurrency and authority remain defined in [SKILL.md](../SKILL.md).

## Ownership

The coordinator resolves the goal, permitted scope, shared contracts and acceptance criteria. It assigns an execution owner and independent reviewer, resolves decisions and verifies the evidence that supports acceptance. Plan/session/handoff operations, bounded identity/status checks and decision records belong in the main chat.

The worker owns the complete permitted execution: implementation, routine diagnosis and reproduction, fixes, integration, mandatory checks, build, inventory/scanner invocation, artifact preparation, accepted commits, and authorized deployment/trial/rollback/cleanup. Divide a package only for a real ownership, dependency, capability or risk boundary, not each shell command or stage. Small work can use one worker sequentially; adding agents is not an acceptance criterion.

The reviewer owns detailed candidate and safety review, finding closure and affected rechecks. Experts resolve material design/diagnostic unknowns. Detailed vulnerability matching or applicability analysis belongs with the qualified expert/reviewer; a worker executes the resulting approved fix or disposition. Existing accepted-risk conditions must be verified, and new risk acceptance beyond current user authority remains a required decision.

## Dispatch and checkpoints

Give the worker the outcome and entire permitted remaining sequence, actual workspace/baseline, allowed files/actions, interfaces, accepted findings, user limits, required checks and recovery requirements. State where it must stop for review or coordinator/user decisions. Delegation grants no authority to upgrade dependencies, waive a gate, accept new risk, push, deploy or delete beyond existing verified user instructions.

Require explicit tool workdirs and a verified candidate/check identity before execution or result acceptance; follow [Check evidence](check-evidence.md). For expensive checks, prefer fast/focused validation, independent review closure, then final full gates, unless the project requires an earlier full gate. Required checks, support matrices and security standards remain unchanged.

For a release package, the worker can prepare and verify an exact artifact, invoke the real safety gate, prepare backups and a concrete cleanup allowlist, and pause with those evidence indexes. The coordinator verifies the artifact/target, actual gate and review results, authorization and recovery/cleanup scope before authorizing the next step. The worker then performs the approved deployment/trial and post-acceptance cleanup. A blocked gate prevents release; missing approval prevents dependent execution. Evidence preparation may continue within its authorized scope.

Keep the worker responsible while a fix, checkpoint or authorized subsequent stage remains. After an accepted source commit, reuse it for the remaining package or explicitly assign a release worker. Neither path makes SOL the default release executor.

## Verification and reports

A result summary identifies the package, changed scope, exact candidate/commit and relevant input hashes, actual required-check results, independent-review status, unresolved issues or requested decision, next permitted step and absolute evidence paths. Detailed code analysis, raw scans, command output and investigation history stay in evidence files or the responsible agent's context. Fetch only the sections needed to verify a decision; a “passed” summary alone is insufficient.

Use one current candidate/status entry per package and durable manifest/receipt indexes. Root verification can be small and targeted without reconstructing the worker's complete investigation. A missing, stale or contradictory index goes back to its owner for correction; do not compensate by repeatedly loading whole histories, raw inventories or superseded plans into SOL.

The coordinator independently checks:

- Original user authority, current limits and the exact target/action to authorize.
- Complete task-diff and artifact identities, including dirty/untracked inputs and relevant configuration.
- Required commands actually ran on those inputs; success, failures and exceptions match the original logs and current candidate.
- Required independent review covers the scope, confirmed findings are closed, and any risk acceptance is already authorized or pending.
- Mandatory integration/final-state gates and, for external changes, backups/rollback and exact cleanup scope are satisfied.

Use relevant source/diff/log inspection and proportionate spot checks; expand when evidence is missing, contradictory, stale or high risk demands it. Send routine re-execution or deeper investigation to the responsible worker/reviewer/expert with the exact gap. Preserve the project's full acceptance/security standard; narrowing what enters SOL's context does not narrow what must be checked.

## Capability gaps and handoff

Resolve an unavailable worker capability with another authorized executor or supported tool. If none can perform the step, mark that step blocked and preserve evidence; do not silently move an entire package into the main chat. An explicit user instruction or a genuinely coordinator-only operation can justify a narrow direct execution exception. Record why, the exact scope and unchanged acceptance/security checks; return subsequent execution to the worker. This exception grants no additional authority or model substitution.

Record verified conditional model fallbacks, scoped gate exceptions and privacy limits with their original user source, exact scope/conditions and current status. Reuse unchanged approvals across handoffs; repeated capacity failures alone grant no model substitution. A Core-only exception does not cover UI or new risks. Apply candidate-specific limits only when the original user imposed them; do not invent reapproval requirements for fixes within unchanged scope/conditions. Preserve actual pending decisions and later human replies with their source rather than treating a stale Handoff's pending label as current authority.

Within existing authority, workers collect bounded counts/error codes and reproduce confirmed failures using available diagnostic tools. Protect private content and user data. Reserve user requests for steps the human actually must complete (such as an OS prompt or new credential entry), unresolved unsaved-data risk or product changes requiring explicit approval; do not repeatedly ask the user to reconfirm an already established symptom.

Handoff records the unfinished package, its decision/checkpoint status, last accepted candidate/evidence, stopped writers and the next authorized execution step. The successor verifies ownership, authority and native startup budget, then assigns only the unfinished execution to a worker. Reuse valid evidence instead of rediscovering or replaying completed stages. Coordinator/worker/reviewer changes and completed stages do not themselves require a new main chat.

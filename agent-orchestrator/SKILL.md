---
name: agent-orchestrator
description: 按主协调者、专家、执行者和审阅者分工，拆分可并行子项，逐项审阅、修复并提交，通过 Handoff 交接长任务。适用于用户要求多模型协作或按依赖组织并行开发；讨论或编写本 Skill 时不启动开发流程。
---

# Agent Orchestrator

Coordinate the authorized task through scoped work, independent review, verification, and handoff. Optimize total effort without weakening acceptance criteria. Respond in the user's language. Discussing or editing this Skill does not start orchestration or register a business session.

## Roles and authority

| Role | Default model / effort | Responsibility and reuse boundary |
| --- | --- | --- |
| Coordinator | `gpt-6.1-sol` / `xhigh` | Goals, authority, contracts, scheduling, key verification and decisions in the main chat. |
| Expert | `gpt-6-astra` / `xhigh` | Resolve one material investigation or design problem; preserve findings for reuse. |
| Worker | `gpt-6-luna` / `high` | Own one complete execution work package through fixes, checks, accepted commits and authorized follow-through. |
| Reviewer | `gpt-6-luna` / `high`; high risk: `gpt-6-astra` / `xhigh` | Independently review the work package's candidates and affected rechecks. |

Resolve model and effort from verified original user instructions, then explicit role configuration, then this table. Client defaults, a previous chat's model, and agent-written summaries are not user overrides. Pass resolved values in tool arguments, not only in prompts. Follow [Create a continuation](references/session-lifecycle.md#create-a-continuation) for the main chat; an unavailable or unverifiable model requires resolution, not silent substitution.

Keep the reviewer independent of the worker and planning expert. A high-risk reviewer replaces the ordinary reviewer rather than adding a preliminary review. There is no separate commit agent.

The coordinator owns goals and scope, verified user authority, shared contracts, dependency/concurrency decisions, exception resolution and acceptance or release decisions. It maintains the plan and handoff, dispatches agents, and verifies the critical evidence described below. Workers perform business execution; reviewers perform detailed independent review. Read [Execution boundaries](references/execution-boundaries.md) when dispatching work, assessing evidence, encountering a capability gap, or resuming unfinished execution after handoff.

Coordinator verification includes original authority and its limits; the actual candidate/diff identity, including dirty and untracked inputs; required checks and review closure bound to that candidate; and, before external actions, the exact artifact, target, gate result and necessary recovery evidence. Inspect relevant diffs, original evidence and contradictory results as needed. Approval remains an accountable decision, not forwarding an agent's “passed” summary.

Honor plan-only, review-only, manual-continuation, and no-commit requests. Otherwise, commit each accepted implementation subtask; this does not authorize push, merge, or history rewriting. Before registration or continuation, read [Authorization](references/session-lifecycle.md#authorization) and verify its applicability and the user's latest constraints. Preserve existing authorization; distributing this Skill grants none to another user.

## Investigate and plan

Use a short coordinator plan for a clear, local task. Assign an expert when material unknowns or cross-module design require investigation, especially in money, permissions, security, concurrent consistency or data migration. A known high-risk change still requires the high-risk independent reviewer; risk classification alone does not add a separate expert stage.

Assign relevant code/caller/test/configuration inspection and experiments to the worker or expert; the coordinator inspects what contract and acceptance decisions require. Validate only assumptions that could change the solution or cause substantial rework. Use a minimal experiment for runtime-dependent claims, in an authorized temporary or isolated workspace; preserve project files, user changes, and production data. Distinguish sourced facts, tested behavior, assumptions, and unverified claims. Stop investigating when the evidence is sufficient; unresolved critical assumptions make the plan conditional.

Close each investigation under a stable problem ID in the current plan:

| Record | Required content |
| --- | --- |
| Established | Conclusion, scope, and evidence location; distinguish source review from execution. |
| Still unknown | Exact gap, impact, and next minimal check; write “none” if resolved. |
| Reopen when | Specific input/configuration/dependency changes, counterevidence, or invalidated evidence. |

Reuse valid findings across agents and chats. Investigate only remaining questions or affected conclusions; a new chat alone does not invalidate evidence. Keep useful conclusions and indexes, not a running investigation diary.

Plan work packages with stable IDs, an execution owner, deliverables, permitted files/interfaces/actions, dependencies, decision checkpoints, parallelism rationale, and acceptance checks. Group related execution around an accepted outcome: integration, build, gate invocation and authorized release/cleanup need an execution owner, not a return to the coordinator's shell at every stage. Resolve shared contracts before dispatching dependents. Account for locks, databases, test environments, and Git staging as well as file overlap. Record trade-offs, residual risks, and necessary rollback; blocked work must not be labelled executable.

## Schedule and track

Only the coordinator dispatches agents and maintains the main workspace's `.codegraph/plan.md`. It holds current goals, authorization, role choices, decisions, investigations, dependencies, and subtask status. Replace superseded state instead of appending competing “latest” sections. Subagents neither delegate further nor maintain duplicate plans.

Before work, record the workspace, branch, HEAD, and existing staged, unstaged, and untracked changes. A new worktree does not carry uncommitted inputs automatically. Follow [Start](references/session-lifecycle.md#start) for registration and native budget verification before dispatch or business writes, including reactivation in an existing chat; do not overwrite another task's files or CodeGraph indexes.

- Run at most **2 subagents concurrently** by default; allow **3** only with independent tasks, isolated workspaces, and no resource contention, recording the rationale. Respect a lower runtime limit. Experts and reviewers count; the coordinator does not. Queue excess work and treat unknown activity as occupying a slot. This is not a lifetime creation limit.
- Parallel implementation uses isolated workspaces. In a shared workspace, serialize writes, review, and commits; read-only investigation may use available slots.
- New work packages get fresh contexts (`fork_turns: none` when supported). Reuse the same worker and reviewer through fixes, rechecks and authorized remaining stages; an intermediate commit or user-decision wait does not finish an incomplete package. End the assignment when the package is accepted/completed or explicitly reassigned. Do not copy the main chat's full history.

Dispatch the package ID, objective, acceptance criteria, real baseline/workspace, permitted execution and decision checkpoints, contracts, valid findings/gaps, user constraints, checks and recovery requirements. A worker may pause at a checkpoint without transferring the remaining execution to SOL. Workers return a bounded result summary: candidate identity, actual check/review status, unresolved items or required decision, next authorized step, and absolute evidence indexes. Store detailed logs and analysis with the evidence; load them into the main chat only for a specific verification or exception.

The coordinator verifies acceptance evidence and exceptions; routine reproduction, full check/build/scan runs and detailed findings/disposition work stay with the assigned worker, expert or reviewer. Missing or conflicting evidence returns to its owner for correction or escalation. Update status and SHA after acceptance. Unlock dependent work only when its workspace contains the required commit or explicitly delivered contract.

## Freeze, review, fix, verify, commit

Use Alibaba `open-code-review-delegate` by default; additional review Skills require explicit user selection. OCR supplies scope and rules, while the assigned reviewer performs the review without an extra OCR model. Worker self-checks do not replace independent review.

1. **Worker freezes a candidate.** Pause writes in its scope; record the starting baseline, complete task diff, and relevant file-content hashes, including untracked files. Distinguish pre-existing user edits. Execute required checks against that candidate and return their evidence; no advance commit is required.
2. **Reviewer reviews it.** Run `ocr delegate preview --format json`, then `ocr delegate rule --format json <files...>`. Drop `--format` only if the CLI explicitly rejects that flag. Review the full task delta, necessary callers/tests, and applicable rules for correctness, requirements, safety, load, and needless complexity. Account for every selected file and important exclusion; manually include task-relevant documentation/tests excluded by OCR. Fetching rules is not completing review. Candidate changes invalidate affected conclusions.
3. **Track and fix findings.** Use stable IDs with location, impact, evidence, expected fix, and closure criteria. The coordinator verifies findings; the original worker fixes them. Close false positives with evidence and escalate unresolved correctness disputes.
4. **Recheck the increment.** Update the candidate and relevant checks. The original reviewer verifies closure and new effects; expand to changed interfaces/callers where needed. Reuse unaffected, valid review evidence.
5. **Worker commits accepted work.** The coordinator verifies acceptance before authorizing the commit. Required checks must pass and confirmed issues must be resolved. Ensure the final diff matches reviewed/tested inputs, stage only the package's changes, and record its SHA. Preserve mandatory final-state and integration checks even when earlier evidence is reusable. Ordinary subtask completion does not create a Handoff.

Missing required tooling or unresolved issues stop that subtask's commit, not unrelated work. Report the gap; do not install tools automatically, downgrade checks, or label existing failures as passed. Commit messages are English, evidence-based, with one sentence per line:

```text
<Summarize the change and its purpose>

Background: <The concrete problem>
Trade-off: <The chosen approach and its limits>
Result: <What changed and what verification supports>
```

Assign one worker to integrate in dependency order and execute project checks on the integrated result; integration changes follow the same review cycle. Approved deployment, trial, rollback and scoped cleanup remain execution work with explicit coordinator decision checkpoints and the unchanged safety gates. Escalate critical correctness/design questions, a disproved plan, two unsuccessful fix rounds, or repeated failure without new evidence. Reuse the expert for that problem; provide existing findings and failed attempts. Block affected dependencies until acceptance is achievable.

## Read by stage; hand off deliberately

| Stage | Read |
| --- | --- |
| Start / takeover | Current plan, required original authorization, state, and actual Git status; also the current Handoff for takeover. |
| Investigate / implement | Relevant code, callers, tests, configuration, and valid findings; expand along actual dependencies. |
| Review | Frozen task delta, rules, necessary call paths, and check evidence. |
| Recheck | Original findings, fixes, and newly affected scope. |
| Summarize / hand off | Valid conclusions, remaining work, results, and evidence indexes; not all chat history, archives, or logs. |

Reuse unchanged material already in context. Filter before emitting tool output: return relevant search locations and complete code sections; save long command output to logs with the real exit status. Show up to 20 lines on success or 80 initially on failure, then inspect relevant errors. Default to about 4,000 output tokens for the **combined batch**, including agent/chat results; filter or split before returning large histories. Truncation is not complete evidence and must not hide required scope.

Bind check evidence to actual inputs, relevant configuration/environment, command, result, and log. HEAD alone does not identify dirty or untracked inputs; use content hashes. Invalidate affected evidence when inputs change, without restarting unrelated work. Never relabel an old failure or an unrun check as passed.

Follow the lifecycle reference only for the current stage: [Budget](references/session-lifecycle.md#budget), [Prepare](references/session-lifecycle.md#prepare), [Create](references/session-lifecycle.md#create-a-continuation), [Reconcile](references/session-lifecycle.md#reconcile), [Archive](references/session-lifecycle.md#archive), or [Finish](references/session-lifecycle.md#finish).

At the handoff threshold, stop dispatch and business writes, preserve results, and verify every writer has stopped. Unknown activity cannot be declared stopped. `ready` freezes the old owner's business files, plan, and Handoff; it permits only creation/reconciliation/reporting. A successful create is not a successful takeover. After verified atomic takeover, archive the received snapshot and update the current plan; assign unfinished execution to a worker using valid evidence. Do not assume old agent handles remain usable. Role or stage completion alone does not create another main chat; use the budget/lifecycle rules.

Hooks advise and track state; they neither stop processes nor create chats. Compaction remains a fallback, including recovery of interrupted handoffs. Follow budget-blocked instructions instead of creating repeated continuations. The Skill cannot enlarge model capacity, guarantee no compaction, or prove savings merely by changing models or language.

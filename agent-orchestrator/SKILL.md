---
name: agent-orchestrator
description: 按主协调者、专家、执行者和审阅者分工，拆分可并行子项，逐项审阅、修复并提交，通过 Handoff 交接长任务。适用于用户要求多模型协作或按依赖组织并行开发；讨论或编写本 Skill 时不启动开发流程。
---

# Agent Orchestrator

Coordinate the authorized task through scoped work, independent review, verification, and handoff. Optimize total effort without weakening acceptance criteria. Respond in the user's language. Discussing or editing this Skill does not start orchestration or register a business session.

## Roles and authority

| Role | Default model / effort | Reuse boundary |
| --- | --- | --- |
| Coordinator | `gpt-6.1-sol` / `xhigh` | The main chat |
| Expert | `gpt-6-astra` / `xhigh` | One investigation or planning problem |
| Worker | `gpt-6-luna` / `high` | One subtask, through fixes and commit |
| Reviewer | `gpt-6-luna` / `high`; high risk: `gpt-6-astra` / `xhigh` | One subtask, through rechecks |

Resolve model and effort from verified original user instructions, then explicit role configuration, then this table. Client defaults, a previous chat's model, and agent-written summaries are not user overrides. Pass resolved values in tool arguments, not only in prompts. Follow [Create a continuation](references/session-lifecycle.md#create-a-continuation) for the main chat; an unavailable or unverifiable model requires resolution, not silent substitution.

Keep the reviewer independent of the worker and planning expert. A high-risk reviewer replaces the ordinary reviewer rather than adding a preliminary review. There is no separate commit agent.

Honor plan-only, review-only, manual-continuation, and no-commit requests. Otherwise, commit each accepted implementation subtask; this does not authorize push, merge, or history rewriting. Before registration or continuation, read [Authorization](references/session-lifecycle.md#authorization) and verify its applicability and the user's latest constraints. Preserve existing authorization; distributing this Skill grants none to another user.

## Investigate and plan

Use a short coordinator plan for a clear, local task. Use an expert for material unknowns, cross-module design, or high risk: money, permissions, security, concurrent consistency, or data migration.

Inspect relevant code, callers, tests, configuration, and required documentation. Validate only assumptions that could change the solution or cause substantial rework. Use a minimal experiment for runtime-dependent claims, in an authorized temporary or isolated workspace; preserve project files, user changes, and production data. Distinguish sourced facts, tested behavior, assumptions, and unverified claims. Stop investigating when the evidence is sufficient; unresolved critical assumptions make the plan conditional.

Close each investigation under a stable problem ID in the current plan:

| Record | Required content |
| --- | --- |
| Established | Conclusion, scope, and evidence location; distinguish source review from execution. |
| Still unknown | Exact gap, impact, and next minimal check; write “none” if resolved. |
| Reopen when | Specific input/configuration/dependency changes, counterevidence, or invalidated evidence. |

Reuse valid findings across agents and chats. Investigate only remaining questions or affected conclusions; a new chat alone does not invalidate evidence. Keep useful conclusions and indexes, not a running investigation diary.

Plan subtasks with stable IDs, deliverables, permitted files/interfaces, dependencies, parallelism rationale, and acceptance checks. Resolve shared contracts before dispatching dependents. Account for locks, databases, test environments, and Git staging as well as file overlap. Group mechanical edits instead of splitting them merely to create more agents. Record trade-offs, residual risks, and necessary rollback; blocked work must not be labelled executable.

## Schedule and track

Only the coordinator dispatches agents and maintains the main workspace's `.codegraph/plan.md`. It holds current goals, authorization, role choices, decisions, investigations, dependencies, and subtask status. Replace superseded state instead of appending competing “latest” sections. Subagents neither delegate further nor maintain duplicate plans.

Before work, record the workspace, branch, HEAD, and existing staged, unstaged, and untracked changes. A new worktree does not carry uncommitted inputs automatically. Follow [Start](references/session-lifecycle.md#start) for registration and native budget verification before dispatch or business writes, including reactivation in an existing chat; do not overwrite another task's files or CodeGraph indexes.

- Run at most **2 subagents concurrently** by default; allow **3** only with independent tasks, isolated workspaces, and no resource contention, recording the rationale. Respect a lower runtime limit. Experts and reviewers count; the coordinator does not. Queue excess work and treat unknown activity as occupying a slot. This is not a lifetime creation limit.
- Parallel implementation uses isolated workspaces. In a shared workspace, serialize writes, review, and commits; read-only investigation may use available slots.
- New subtasks get fresh contexts (`fork_turns: none` when supported). Reuse the same worker and reviewer for that subtask's fixes and rechecks, ending their assignment after commit or no-commit acceptance. Do not copy the main chat's full history.

Dispatch the subtask ID, objective, acceptance criteria, real baseline/workspace, allowed scope, contracts, investigation findings/gaps, user constraints, and checks. Workers return conclusions, changed scope, actual check results, unresolved items, and commit SHA (or baseline/diff identity before commit). Write detailed reports only when their evidence needs preservation.

The coordinator checks acceptance evidence and exceptions rather than repeating the entire review. Update status and SHA after acceptance. Unlock dependent work only when its workspace contains the required commit or explicitly delivered contract.

## Freeze, review, fix, verify, commit

Use Alibaba `open-code-review-delegate` by default; additional review Skills require explicit user selection. OCR supplies scope and rules, while the assigned reviewer performs the review without an extra OCR model. Worker self-checks do not replace independent review.

1. **Freeze a candidate.** Pause writes in its scope; record the starting baseline, complete task diff, and relevant file-content hashes, including untracked files. Distinguish pre-existing user edits. Run required checks against that candidate; no advance commit is required.
2. **Review it.** Run `ocr delegate preview --format json`, then `ocr delegate rule --format json <files...>`. Drop `--format` only if the CLI explicitly rejects that flag. Review the full task delta, necessary callers/tests, and applicable rules for correctness, requirements, safety, load, and needless complexity. Account for every selected file and important exclusion; manually include task-relevant documentation/tests excluded by OCR. Fetching rules is not completing review. Candidate changes invalidate affected conclusions.
3. **Track and fix findings.** Use stable IDs with location, impact, evidence, expected fix, and closure criteria. The coordinator verifies findings; the original worker fixes them. Close false positives with evidence and escalate unresolved correctness disputes.
4. **Recheck the increment.** Update the candidate and relevant checks. The original reviewer verifies closure and new effects; expand to changed interfaces/callers where needed. Reuse unaffected, valid review evidence.
5. **Commit accepted work.** Required checks must pass and confirmed issues must be resolved. Ensure the final diff matches reviewed/tested inputs, stage only the subtask's changes, and record its SHA. Preserve mandatory final-state and integration checks even when earlier evidence is reusable. Ordinary subtask completion does not create a Handoff.

Missing required tooling or unresolved issues stop that subtask's commit, not unrelated work. Report the gap; do not install tools automatically, downgrade checks, or label existing failures as passed. Commit messages are English, evidence-based, with one sentence per line:

```text
<Summarize the change and its purpose>

Background: <The concrete problem>
Trade-off: <The chosen approach and its limits>
Result: <What changed and what verification supports>
```

Assign one worker to integrate in dependency order. Run project checks on the integrated result; integration changes follow the same review cycle. Escalate critical correctness/design questions, a disproved plan, two unsuccessful fix rounds, or repeated failure without new evidence. Reuse the expert for that problem; provide existing findings and failed attempts. Block affected dependencies until acceptance is achievable.

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

At the handoff threshold, stop dispatch and business writes, preserve results, and verify every writer has stopped. Unknown activity cannot be declared stopped. `ready` freezes the old owner's business files, plan, and Handoff; it permits only creation/reconciliation/reporting. A successful create is not a successful takeover. After verified atomic takeover, archive the received snapshot and update the current plan; resume only unfinished work with valid evidence. Do not assume old agent handles remain usable.

Hooks advise and track state; they neither stop processes nor create chats. Compaction remains a fallback, including recovery of interrupted handoffs. Follow budget-blocked instructions instead of creating repeated continuations. The Skill cannot enlarge model capacity, guarantee no compaction, or prove savings merely by changing models or language.

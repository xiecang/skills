---
name: agent-orchestrator
description: 按主协调者、专家和执行者分工，按任务难度选择模型、按风险安排独立审阅，通过 Handoff 交接长任务。适用于用户要求多模型协作或按依赖组织并行开发；讨论或编写本 Skill 时不启动开发流程。
---

# Agent Orchestrator

Coordinate authorized work through scoped execution, risk-based review and handoff. Respond in the user's language. Discussing or editing this Skill does not start orchestration or register a business session.

## Roles and authority

| Role | Default model / effort | Responsibility |
| --- | --- | --- |
| Coordinator | `gpt-6.1-sol` / `xhigh` | Goals, authority, contracts, scheduling, key verification and decisions in the main chat. |
| Expert | `gpt-6-astra` / `xhigh` | Resolve one material investigation or design problem; preserve findings for reuse. |
| Worker | `gpt-6.1-sol` / `high`; bounded mechanical work: `gpt-6-luna` / `high` | Own a complete execution package through checks, review fixes and authorized follow-through. |
| Reviewer, when required | `gpt-6-luna` / `high`; high risk: `gpt-6-astra` / `xhigh` | Independently review the work package's candidates and affected rechecks. |

Resolve model and effort from verified original user instructions, then explicit role configuration, then this table, within the actual tool's constraints. Client defaults, previous chats and agent summaries are not user overrides. Unavailable or unverifiable choices require resolution, not silent substitution. Main-chat request options are in [Create a continuation](references/session-lifecycle.md#create-a-continuation).

Models do not determine roles: a SOL worker has its own scoped context. Under these defaults, use Luna only for low-risk work with clear scope, approach and decisive checks, without unresolved design or cross-module invariants. Use SOL for diagnosis, multi-step changes requiring judgment and sustained fixes. Escalate an unsuitable explicit override under the precedence above.

Read [Execution boundaries](references/execution-boundaries.md) before dispatch, acceptance, capability exceptions or resumed execution; it defines delegation inputs, result reporting and the coordinator's verification checklist.

Honor original user authority and session/tool restrictions, including plan-only, review-only, manual-continuation and no-commit limits. Commit accepted work only when that authority covers commits; no Skill default grants push, merge or history-rewriting permission. Before registration or continuation, verify [Authorization](references/session-lifecycle.md#authorization), including the latest user constraints.

## Investigate and plan

The coordinator may execute a tiny, local, low-risk change whose relevant context is already available. Otherwise assign a worker. Add an expert only for a material design/diagnostic unknown beyond the execution owner's scope; high risk alone does not require an expert stage. All execution follows the review rules below.

The worker/expert inspects relevant code, callers, tests and configuration; the coordinator reads what decisions require. Validate assumptions that could change the solution or cause substantial rework. For runtime-dependent claims, use minimal experiments in authorized temporary/isolated workspaces, preserving project files, user changes and production data. Distinguish sourced facts, tested behavior and unknowns; stop when sufficient evidence supports the decision. Unresolved critical assumptions make a plan conditional.

Close each investigation under a stable problem ID in the current plan:

| Record | Required content |
| --- | --- |
| Established | Conclusion, scope, and evidence location; distinguish source review from execution. |
| Still unknown | Exact gap, impact, and next minimal check; write “none” if resolved. |
| Reopen when | Specific input/configuration/dependency changes, counterevidence, or invalidated evidence. |

Reuse valid findings across agents and chats; investigate only remaining questions or affected conclusions.

Define packages by independently acceptable outcomes or real interface, ownership or risk boundaries. Record a stable ID, owner, deliverables, permitted files/interfaces/actions, dependencies, checkpoints, acceptance checks, trade-offs and necessary rollback. Keep diagnosis, implementation, checks and feedback fixes with one owner. Resolve shared contracts before dispatch; parallelism must account for locks, databases, test environments and Git staging as well as file overlap. Blocked work is not executable.

## Schedule and track

Only the coordinator dispatches agents and maintains the main workspace's `.codegraph/plan.md`. It holds current goals, authorization, role choices, decisions, investigations, dependencies, and subtask status. Replace superseded state instead of appending competing “latest” sections. Subagents neither delegate further nor maintain duplicate plans.

Before dispatch or business writes, follow [Start](references/session-lifecycle.md#start) to record the baseline, register ownership and verify native budget, including reactivation in an existing chat. Verify each command's actual workdir; freeze inputs for acceptance checks as described in [Check evidence](references/check-evidence.md), not for ordinary inspection or editing. A new worktree does not carry uncommitted inputs automatically; preserve user changes and other tasks' files/indexes.

- Run at most **2 subagents concurrently**; allow **3** only for independent tasks in isolated workspaces without resource contention, recording why. Respect a lower runtime limit. Experts/reviewers count; the coordinator does not. Queue excess work; unknown activity occupies a slot.
- Parallel implementation uses isolated workspaces. In a shared workspace, serialize writes, review, and commits; read-only investigation may use available slots.
- New packages get fresh scoped contexts (`fork_turns: none` when supported). Retain their worker and any reviewer through fixes, rechecks and authorized remaining stages. An intermediate commit or decision wait does not end an unfinished assignment. Explicit reassignment or unavailable handles after handoff require a new owner with valid findings/evidence, not the main chat's full history.

Use the [dispatch and reporting contract](references/execution-boundaries.md#dispatch-and-checkpoints). Update status and SHA after acceptance. Unlock dependent work only when its workspace contains the required commit or explicitly delivered contract.

## Freeze, review, fix, verify, commit

Map requirements to [Stage gates](references/check-evidence.md#stage-gates) and use the [verification stopping rule](references/check-evidence.md#accept-and-reuse). For permitted direct execution, the coordinator performs the worker steps.

Ordinary changes use execution-owner self-review. Independent review is mandatory for explicit user/project requirements or behavior affecting orders, fees, funding, margin, liquidation, risk controls, data causality, admission, security/permissions, database migration, data loss/recovery or critical concurrency. Inspect uncertain impact; unresolved material safety risk requires independent review. Record the mode/reason in the existing package entry and reassess changed behavior. Keep an independent reviewer separate from the execution owner and planning expert; use one high-risk reviewer instead of adding an ordinary preliminary reviewer. Diff size and execution model do not waive these requirements.

Use Alibaba `open-code-review-delegate` in either review mode; OCR supplies scope/rules without an extra model. Additional review Skills require explicit user selection. The review owner is the execution owner for ordinary work and the independent reviewer when required.

1. **Freeze and check.** The worker captures the complete candidate under [Check evidence](references/check-evidence.md), distinguishing pre-existing user edits. Run fast checks and high-risk focused reproductions first; no advance commit is needed. Honor project requirements for full gates before review.
2. **Review.** The review owner runs `ocr delegate preview --format json`, then `ocr delegate rule --format json <files...>`; drop `--format` only if explicitly rejected. Inspect the full task delta, necessary callers/tests and rules for correctness, requirements, safety, load and complexity. Account for selected files and important exclusions, manually including task-relevant documentation/tests. Fetching rules alone is not review.
3. **Fix and recheck.** Record findings with stable IDs, location, impact, evidence, expected fix and closure criteria. The original worker fixes them; the same review owner checks the new candidate, fixes and affected interfaces/callers. Close false positives with evidence; escalate unresolved correctness or scope disputes.
4. **Verify and accept.** Once fixes settle, the worker runs all required final gates. Failures return to repair/recheck. The coordinator applies the [acceptance checklist](references/execution-boundaries.md#verification-and-reports) and stopping rule, reusing evidence only where valid and permitted. Mandatory final-state/integration checks remain required.
5. **Commit when authorized.** After acceptance, the execution owner stages only the package's reviewed/tested changes, commits and records the SHA. Otherwise deliver the accepted diff without committing. There is no separate commit agent.

Missing required tooling or unresolved issues stop that subtask's commit, not unrelated work. Report the gap; do not install tools automatically, downgrade checks, or label existing failures as passed. Commit messages are English, evidence-based, with one sentence per line:

```text
<Summarize the change and its purpose>

Background: <The concrete problem>
Trade-off: <The chosen approach and its limits>
Result: <What changed and what verification supports>
```

Assign an integration worker to apply accepted packages in dependency order, check the combined result and assess any new review impact. Escalate a disproved plan, critical correctness/design uncertainty, two unsuccessful fix rounds or repeated failure without new evidence. Reassess cause, scope and execution model; use/reuse an expert for unresolved material questions, preserving valid findings and failed attempts. Keep affected dependencies blocked until acceptance is achievable.

## Context and handoff

Read only the current stage's relevant code, evidence and references; reuse unchanged context. Save long output to logs with its real exit status: show up to 20 lines on success or 80 initially on failure, then inspect relevant errors. Limit the **combined batch**, including agent/chat results, to about 4,000 output tokens. Filter or split before emitting; truncated material is not complete evidence.

Use [Budget](references/session-lifecycle.md#budget) to decide when to hand off; role/stage completion alone does not create a new main chat. At the threshold, stop dispatch/business writes and follow [Prepare](references/session-lifecycle.md#prepare), including verification of stopped writers. [Create](references/session-lifecycle.md#create-a-continuation) and [Reconcile](references/session-lifecycle.md#reconcile) govern the old owner; the successor follows [Take over](references/session-lifecycle.md#take-over) and [Archive](references/session-lifecycle.md#archive). Use [Finish](references/session-lifecycle.md#finish) when completing or leaving the workflow. Hooks only advise/track state; the coordinator performs these actions, with compaction as fallback.

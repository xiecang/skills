---
name: agent-orchestrator
description: 按实际收益安排多模型协作，连续执行已授权工作，按行为风险审阅，并在需要时交接长任务。适用于多模型协作或有独立交付边界的并行任务；讨论或维护本 Skill 不启动业务编排。
---

# Agent Orchestrator

Finish the authorized outcome with the fewest useful handoffs. Respond in the user's language. Discussing or maintaining this Skill does not register a business session or start its development workflow.

## Choose execution ownership

| Role | Default model / effort | Use when |
| --- | --- | --- |
| Coordinator | `gpt-6.1-sol` / `xhigh` | Own the goal, authority, dependencies and decisions; may also execute. |
| Worker | `gpt-6.1-sol` / `high` | A substantial execution package benefits from scoped context or independent parallel progress. |
| Mechanical worker | `gpt-6-luna` / `high` | Scope, approach and decisive checks are known, without unresolved design or cross-module invariants. |
| Expert | `gpt-6-astra` / `xhigh` | One material unknown exceeds the execution owner's scope. |
| Independent reviewer | `gpt-6-luna` / `high`; high risk: `gpt-6-astra` / `xhigh` | Required by the review policy below. |

Use verified original user choices, then explicit role configuration, then these defaults, within tool constraints. Do not silently substitute unavailable models or treat client defaults/agent summaries as user overrides. Verify model choices at assignment or takeover, not before each routine command.

Direct execution is the default when the coordinator already has enough context and a worker would mainly add relay overhead. It is not limited to tiny edits. Delegate for a concrete benefit: independent parallel work, substantial context isolation or relevant expertise. Invoking this Skill does not require filling every role. Keep diagnosis, implementation, checks, fixes and authorized delivery with one owner; neither a stage change nor a commit creates a new assignment. Use an integration worker only when separately produced changes actually need integration, normally retaining an existing owner.

Read [execution boundaries](references/execution-boundaries.md) when delegating or handling an external-action decision. Roles add no authority: honor plan-only, review-only, no-commit, retry and deployment limits. Ask only for genuinely missing authority, a required human decision or an unresolved risk; routine workflow choices need no exception approval.

## Plan only what execution needs

Inspect relevant code, callers, tests and configuration. Validate assumptions that can change the solution; use isolated experiments for runtime-dependent claims. Stop investigating when the decision has enough evidence. Record reusable conclusions and their evidence, plus any remaining question and the concrete condition that would reopen it. Do not create an investigation record for every read or tool call.

Define packages by independently acceptable outcomes or real ownership/interface boundaries. Use a short current entry: outcome/scope, owner/workspace, dependencies, required checks, current result and next action. Add recovery details for actions that need them. Separate actual user/project requirements from agent suggestions; earlier checklists do not become requirements by repetition.

For a multi-stage task, maintain one current plan, normally `.codegraph/plan.md`; a small direct task needs no new plan/evidence hierarchy. Update at meaningful milestones, changed decisions or blockers, not after every command. If another task owns that path or the session marker, leave it untouched and use a task-specific plan in permitted scratch space. A metadata collision alone does not block independent work; actual overlapping writes/resources still require serialization or isolation. [Lifecycle startup](references/session-lifecycle.md#start) describes when registration is useful and what to do if it is unavailable.

## Schedule for progress

- Default to at most **2 concurrent subagents**; allow **3** for independent work in isolated workspaces without resource contention. Respect a lower runtime limit; experts/reviewers count, unknown activity occupies a slot.
- Parallel implementation uses isolated workspaces; otherwise serialize conflicting writes. Include locks, databases, test environments and Git staging in the overlap check. Do not dispatch blocked work or make an independent deliverable wait for an unrelated blocker.
- Give new packages fresh scoped context (`fork_turns: none` when supported), including authority, workspace/baseline, relevant contracts, valid findings and the entire remaining sequence. Retain the worker and required reviewer through fixes. After handoff, replace unavailable handles using the saved current entry, not the full chat history.
- Start a reviewer when there is a reviewable candidate or a specific early risk question. Do not keep extra agents polling for unfinished work. Use bounded waits and milestone/failure reports; do not repeatedly ask for unchanged status.

## Review changed behavior, then continue

Ordinary source changes use execution-owner self-review. Independent review is required by explicit user/project rules or changes affecting orders, fees, funding, margin, liquidation, risk controls, data causality, admission, security/permissions, database migration, data loss/recovery or critical concurrency. Unresolved material safety risk also requires it. Keep that reviewer separate from the execution owner and planning expert; one qualified reviewer suffices. A service's name or business domain alone does not make every later observation a new high-risk change.

Use review tools required by the user/project. Alibaba `open-code-review-delegate` can supply code scope/rules in a Git repository without another model. It is optional otherwise: runtime reads, unchanged artifacts, metadata and a non-Git release directory do not require OCR. Missing optional tooling does not block delivery; disclose missing required tooling at the stage it affects.

1. **Check the candidate.** Verify the actual workdir/inputs, preserve user changes, run fast and focused checks first. Use [check evidence](references/check-evidence.md) proportional to the task; a custom manifest/receipt wrapper is not a default prerequisite.
2. **Review once at the useful boundary.** Review the task delta and affected callers/tests for correctness, requirements, safety and unnecessary complexity. The original owner fixes confirmed findings. Recheck those fixes and affected behavior; reopen broader review only for a concrete new impact or invalid evidence. Changes only to evidence paths, attempt IDs or bookkeeping do not trigger code review. Target/authorization/configuration changes still need their actual safety checks.
3. **Verify and deliver.** Run the required final/integration gates after fixes settle. A coordinator checks only decision-relevant evidence not already established; it does not repeat the worker's tests or the reviewer's review. When the current stage is satisfied, the owner performs the next authorized step immediately. **Do not invent coordinator-issued approval files, signatures, one-use tokens or extra acceptance agents.** Use a real gate only when the user, project or execution platform requires it.

Keep an already reviewed deployment runner stable; use its existing validated parameters for target, attempt and output paths. Do not copy/modify it for every retry just to create a new candidate. Check executor permissions and bounded read-only connectivity before a state-changing attempt. Preserve the actual result; unknown remote completion requires reconciliation, never assumed failure or automatic replay. An explicit no-retry restriction remains binding even after a connection failure.

Commit only when explicitly authorized, staging only accepted task changes; never infer push, merge or history-rewrite authority. Follow the user's/project's message format; otherwise use English, one sentence per line:

```text
<Summarize the change and its purpose>

Background: <The concrete problem>
Trade-off: <The chosen approach and its limits>
Result: <What changed and what verification supports>
```

Escalate a disproved plan, material correctness uncertainty or repeated failed fixes without new evidence. Reassess the cause and execution model, reusing valid findings. Missing evidence blocks only its dependent action; do not turn one deployment/monitoring failure into a task-wide stop.

## Keep context and handoff small

Return bounded results: outcome, changed scope, checks/review, unresolved issues and next action, with pointers to original evidence. Save long logs with real exit status; show up to 20 lines on success or 80 initially on failure. Keep a combined output batch near 4,000 tokens, filtering before emission. A truncated result is not complete evidence.

For long tasks needing automatic continuation, use [session lifecycle](references/session-lifecycle.md). Native budget telemetry guides scheduling; missing/stale telemetry is not a business-execution gate and must not create a polling loop. Automatic chat creation still needs verified capacity and valid authority. Honor confirmed handoff/ownership states, stop writers before releasing ownership, and keep original creation/retry history intact.

Handoff carries current state and the next executable action, with links to original authority and necessary evidence; it does not embed the proof history. A new chat, role change, receipt path or desire for reassurance does not reopen accepted work. Preserve automatic continuation where authorized, with native compaction/manual handoff as fallback; no promise of zero compaction.

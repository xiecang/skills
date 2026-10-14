# Independent role forward-test

Give an independent agent the current `SKILL.md`, `references/execution-boundaries.md`, `references/session-lifecycle.md` and `tests/role_scenarios.json`. Ask it to answer every scenario from those inputs, without reading `test_role_contract.py` or its expected decisions. This is a plan-only maintenance exercise: no real dispatch, session registration, deployment, cleanup or source/configuration writes. Save answers only in a temporary directory.

Return a JSON object with `policy_sha256` and `responses`. `responses` maps each scenario ID to exactly one answer; its `owners` object maps every listed action to `coordinator`, `worker`, `expert` or `reviewer`. Include a nonempty `rationale` explaining the independent judgment.

Compute `policy_sha256` by updating one SHA-256 with each relative filename, a NUL byte, and the raw file bytes, in this order: `SKILL.md`, `references/execution-boundaries.md`, `references/session-lifecycle.md`, `tests/role_scenarios.json`. This binds answers to their actual policy/scenario inputs.

Common answer fields:

- `can_proceed_now`: whether the supplied state permits starting the external release; for a scenario without a release, use false without implying local implementation is blocked.
- `preserve_required_checks`, `preserve_safety_gates`, `new_main_chat_for_stage_completion`: Boolean decisions derived from the Skill and scenario.
- `evidence_handling`: `indexed_with_targeted_inspection`, `summary_only` or `replay_all`.

Where applicable, also return:

- Boolean fields: `retain_worker_for_remaining_stages`, `needs_expert`, `replay_valid_completed_steps`, `accept_summary_without_evidence`, `blocked_execution`, `transfer_whole_package_to_coordinator`, `requires_user_risk_acceptance`. `blocked_execution` means any execution step is blocked; list such steps separately in an optional `blocked_steps` array.
- `reviewer_kind`: `ordinary_independent` or `high_risk_independent`.
- `worker_context`: `full_main_history`, `fresh_scoped_evidence` or `reuse_old_handle`.
- `needed_evidence`: an array describing missing evidence; identify current-candidate check/review evidence as `current_candidate_checks` / `current_candidate_review`.
- `direct_execution_exception`: an object with a nonempty `reason` and a `scope` array of exact action IDs.

Use actual JSON booleans for all decision flags, not nulls, numbers, strings or arrays. Choose values independently; the format does not supply an intended decision. Run the behavioral grader with `ORCHESTRATOR_ROLE_RESPONSES` pointing to that file. Report any failures or ambiguities; missing or stale responses cannot count as completed role validation. These cases test planning decisions, not native tool execution or production safety results.

# Check evidence

Use evidence sufficient to establish the actual candidate and required result. Prefer the project's existing checks, Git/CI records, artifact digests and original tool logs. A bespoke manifest, wrapper, receipt index or acceptance certificate is not required merely because this Skill is active.

## Default record

At a useful acceptance boundary record the actual absolute workspace, candidate/changed scope, command, exit status and original log location. Include relevant dirty/untracked inputs, configuration and environment; a commit SHA alone does not identify uncommitted changes. Keep check inputs stable during execution, and do not credit a result from the wrong workdir, another candidate, an interrupted command or a summary unsupported by its original result.

For deployment, reuse accepted source/build evidence and identify the actual artifact, current target/configuration, authorized action and runtime result. Source checks and live acceptance are different requirements: one cannot substitute for the other. Protect user changes and retain failed or unknown attempt records.

Use one current package entry, with links to original evidence. Do not hash the index, hash the acceptance of that index, or create another review package to certify those records. Hashes identify inputs/artifacts; they do not grant authority or prove that a claim is true.

## Accept and reuse

When the current stage's required checks and applicable review pass on the actual inputs, confirmed findings close and authority holds, perform the next authorized step. Reopen only for a missing mandatory result, contradictory evidence, changed relevant inputs/environment/target, required freshness or a concrete newly discovered risk. A new chat, executor, attempt ID, receipt path or desire for reassurance is not a reason.

Reuse unchanged source review across delivery attempts. A bookkeeping-only change needs no independent review; verify execution parameters and required target/configuration conditions normally. If code or behavior actually changes, recheck affected tests and review findings. Run all user/project-required final gates; do not rerun a whole suite solely because a note or evidence filename changed.

Separate gates by their actual requirement: source acceptance/commit, integration, artifact preparation or live delivery. A later monitoring/rendering blocker does not prevent an independent service deployment whose requirements pass. An agent's earlier checklist is not an authority source. Add checks only for actual requirements or demonstrated impact, and do not waive required checks to shorten the process.

## Optional candidate helper

Use `scripts/candidate_check.py` when concurrent/dirty/external inputs or a project requirement make an explicit snapshot useful and existing project evidence is insufficient. Do not add it around every command. It is an integrity helper, not a sandbox or authorization mechanism.

Stop source writers while capturing/running checks. Use a durable evidence directory outside candidate inputs or in an existing ignored directory. Verify the absolute worktree and expected full HEAD:

```bash
python3 "<SKILL_DIR>/scripts/candidate_check.py" capture --workspace "<WORKTREE>" --head "<VERIFIED_FULL_HEAD>" --output "<EVIDENCE>/candidate-v1.json"
```

The returned manifest SHA-256 identifies all tracked and non-ignored untracked content, modes, deletions and file symlinks. Add `--input "<ABS_FILE>"` for relevant ignored/external files actually consumed by checks. Directory inputs, submodules and broken/directory symlinks need project-native evidence. Build outputs belong to their artifact checks, not the source manifest merely because they exist.

Run the real required command from its actual workdir; the helper verifies inputs before and after execution and records the command, exit, duration and log hash:

```bash
python3 "<SKILL_DIR>/scripts/candidate_check.py" run --manifest "<EVIDENCE>/candidate-v1.json" --manifest-sha256 "<FROZEN_SHA256>" --workdir "<WORKTREE_OR_MEMBER>" --log "<EVIDENCE>/test-v1.log" --receipt "<EVIDENCE>/test-v1.json" -- cargo test --workspace
```

Verify effective targets of scripts, task recipes and manifest flags: a valid wrapper cannot make a wrong-target check valid. Retain original logs and inspect relevant failures; wrapper success alone does not prove the required suite ran.

To credit that receipt later, execute from the same declared workdir:

```bash
python3 "<SKILL_DIR>/scripts/candidate_check.py" verify --manifest "<EVIDENCE>/candidate-v1.json" --manifest-sha256 "<FROZEN_SHA256>" --workdir "<WORKTREE_OR_MEMBER>" --receipt "<EVIDENCE>/test-v1.json" -- cargo test --workspace
```

The helper binds the whole manifest: changed inputs require a new manifest, and old receipts cannot be rebound. Reuse unaffected results only where project-native dependency evidence permits; otherwise rerun the covered checks. Do not weaken this helper's complete-input contract for convenience; choose appropriate project-native evidence when broad coupling adds no value.

Verify pre-commit receipts before HEAD changes, then record the accepted candidate-to-commit mapping. Historical receipts remain historical, not runs on the new commit. Rerun requirements that actually depend on VCS metadata or explicitly require the committed revision.

Do not run daemonizing checks through this helper. It stops its owned process group on interruption; a remaining/unknown group or descendants outliving the leader invalidates the receipt. Verify other writers stopped before ownership release. Interrupted checks never count as passes.

## Recovery and cleanup

Persist evidence needed to continue the task outside volatile temporary storage. Keep the current result, unresolved issue, next action and links to needed evidence in the existing task record. Resolve a material candidate/result conflict using original evidence, not competing prose summaries. Reuse valid checks after compaction; no new manifest or review is required just to restore context.

Keep active inputs and required recovery evidence while they are still needed. Clean up task-generated records only when authorized and no active work depends on them; preserve unrelated user files, project indexes and business artifacts. A user-requested handoff can summarize this same state without creating another lifecycle or approval mechanism.

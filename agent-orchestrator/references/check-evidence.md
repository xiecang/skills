# Workdir and candidate-bound checks

Read before freezing a candidate, running acceptance checks or crediting a previous result. Use the project's existing equivalent if it establishes the same identities; otherwise use `scripts/candidate_check.py`. This helper is an integrity check, not a sandbox, authorization source or replacement for project gates/review.

## Freeze and execute

The worker first verifies the authorized **absolute worktree root**, expected full HEAD, permitted files/actions and required commands. Set the tool's actual `workdir` explicitly for every execution call, including member packages. A path in a prompt or an inherited shell cwd is not verification. Stop on a mismatch; results from Main or another worktree cannot satisfy this candidate's checks even when HEAD matches.

Stop other source writers before capture and throughout the checks. Use a durable, coordinator-approved evidence directory, either outside the worktree or in an existing Git-ignored directory. Keep manifests, logs and receipts under versioned package/candidate names; the helper refuses overwriting files, writing evidence into candidate inputs or Git metadata.

```bash
python3 "<SKILL_DIR>/scripts/candidate_check.py" capture --workspace "<WORKTREE>" --head "<VERIFIED_FULL_HEAD>" --output "<EVIDENCE>/candidate-v1.json"
```

Preserve the returned manifest SHA-256 as the candidate ID. Capture includes all tracked and non-ignored untracked file contents, executable/file modes, deletions and file-symlink identities. Add `--input "<ABS_FILE>"` for relevant ignored/external input files. Directory inputs, submodules and directory/broken symlinks need project-native evidence; incomplete input coverage cannot be called verified. Toolchain, relevant environment and external artifact identities still need the project's normal evidence.

From the declared workdir, execute each actual required command as an argument list after `--`:

```bash
python3 "<SKILL_DIR>/scripts/candidate_check.py" run --manifest "<EVIDENCE>/candidate-v1.json" --manifest-sha256 "<FROZEN_SHA256>" --workdir "<WORKTREE_OR_MEMBER>" --log "<EVIDENCE>/test-v1.log" --receipt "<EVIDENCE>/test-v1.json" -- cargo test --workspace
```

Use the real project command/support matrix, including explicit environment arguments where needed. The example is not a reduced acceptance recipe. The helper rejects wrong cwd, workspace, HEAD or changed inputs before launching, records the real launch workdir/command/exit/log hash and duration, then rechecks inputs. Shells, task recipes, manifest flags and programs can change their own directories or select other inputs: verify their effective target with project-native evidence, prefer direct commands, and never credit the wrong target because this wrapper returned valid. An interrupted check, launch failure or input drift is never valid, including when the child exited zero. Keep the raw log; a wrapper exit or summary alone is insufficient.

## Accept and reuse

Before crediting a result, compare it with the required command and verify the current candidate, declared workdir and original log:

```bash
python3 "<SKILL_DIR>/scripts/candidate_check.py" verify --manifest "<EVIDENCE>/candidate-v1.json" --manifest-sha256 "<FROZEN_SHA256>" --workdir "<WORKTREE_OR_MEMBER>" --receipt "<EVIDENCE>/test-v1.json" -- cargo test --workspace
```

Execute verification from that workdir too. This binds the result to actual inputs, not merely a commit or a claimed pass. It does not establish that every required command ran, authorize a waiver, make logs tamper-proof against an actor with the same filesystem access, or prove an unchanged environment. The coordinator still verifies scope/completeness, relevant original log sections, review closure and project-specific security/artifact requirements.

Changed inputs require a new frozen manifest and affected rechecks/review; preserve old receipts as historical evidence. Reuse valid unaffected evidence only where project requirements permit, retaining mandatory final-state/integration checks. Never relabel results from a wrong directory or interrupted run as passed. Do not run background/daemonizing checks through this helper; SIGINT stops its owned process group, but the coordinator must still verify all relevant writers/processes stopped before handoff.

Verify pre-commit receipts while their frozen HEAD is still current, then record acceptance and the resulting commit. Committing changes HEAD, so direct verification of the old manifest will reject it even if file bytes match. Independently verify the accepted candidate-to-commit mapping, including preserved on-disk inputs and the approved task delta; retain the original receipts without relabelling them as runs on the new HEAD. Follow project reuse rules and rerun checks whose inputs include changed VCS metadata or whose final gate requires the committed revision. Capture a fresh manifest for new checks/builds at that revision; this helper never silently rebinds historical receipts.

Interrupt cleanup waits for the owned process group, not just its leader, and escalates to SIGKILL after the grace period. A remaining/unknown group sets `process_group_stopped=false`; wrapper termination alone is not proof that handoff is safe. A leader that exits while its descendants remain also yields an interrupted, invalid receipt. Caller verification of detached/other writers remains mandatory.

## Keep one current evidence entry

The current plan has one entry per package: workspace, current candidate manifest/digest, stage, valid/failed/interrupted/unrun checks with receipt paths, review/finding status, scoped decisions and next action/owner. Replace superseded entries instead of appending a competing current-status correction. Keep raw logs, inventories and detailed diagnosis with the worker/reviewer evidence; send SOL a bounded summary plus absolute indexes.

Generate the Handoff synopsis from those verified entries and validate referenced candidate/check identities before `prepare-handoff`. A Handoff's file digest proves transport integrity, not that its statements are current. Conflicting manifest IDs or stale hashes block acceptance/dependent execution until reconciled. Preserve received/archived snapshots byte-for-byte; after takeover correct the active plan without rewriting history. Persist required evidence before ownership release; essential continuity must not depend only on volatile `/tmp` files. None of these summaries or receipts grants user authority or changes a safety gate.

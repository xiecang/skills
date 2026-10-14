"""Run real commands in temporary Git worktrees; never inspect business projects."""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/candidate_check.py"


class CandidateCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="candidate-check-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "项目 with spaces"
        self.root.mkdir()
        self.evidence = self.base / "evidence"
        self.source = self.root / "source.txt"
        self.source.write_text("original\n")
        (self.root / ".gitignore").write_text(".evidence/\nignored.txt\n")
        self.git("init", "--quiet")
        self.git("config", "user.name", "Candidate test")
        self.git("config", "user.email", "candidate@example.invalid")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Temporary baseline")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        self.manifest = self.evidence / "candidate.json"
        self.log = self.evidence / "check.log"
        self.receipt = self.evidence / "receipt.json"
        self.marker = self.base / "executed"
        self.command = [sys.executable, "-c", "from pathlib import Path; "
                        + "Path(" + repr(str(self.marker)) + ").write_text('ran'); print('checked')"]

    def git(self, *args):
        return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args],
                              cwd=self.root, capture_output=True, text=True, check=True)

    def call(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=cwd or self.root,
                              capture_output=True, text=True)

    def capture(self, *extra):
        result = self.call("capture", "--workspace", str(self.root), "--head", self.head,
                           "--output", str(self.manifest), *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.digest = json.loads(result.stdout)["manifest_sha256"]

    def check_args(self, action="run", command=None):
        args = [action, "--manifest", str(self.manifest), "--manifest-sha256", self.digest,
                "--workdir", str(self.root), "--receipt", str(self.receipt)]
        if action == "run":
            args += ["--log", str(self.log)]
        return [*args, "--", *(self.command if command is None else command)]

    def test_capture_run_and_verify_bind_real_workdir_inputs_command_and_log(self):
        self.capture()
        result = self.call(*self.check_args())
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt["workspace"], str(self.root))
        self.assertEqual(receipt["workdir"], str(self.root))
        self.assertEqual(receipt["head"], self.head)
        self.assertEqual(receipt["command_exit"], 0)
        self.assertIs(receipt["valid"], True)
        self.assertEqual(receipt["log_sha256"], hashlib.sha256(self.log.read_bytes()).hexdigest())
        self.assertEqual(self.call(*self.check_args("verify")).returncode, 0)

    def test_same_head_wrong_worktree_is_rejected_before_command(self):
        self.capture()
        other = self.base / "other-worktree"
        self.git("worktree", "add", "--quiet", "--detach", str(other), self.head)
        result = self.call(*self.check_args(), cwd=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.receipt.exists())

    def test_capture_from_wrong_cwd_or_unverified_head_is_rejected(self):
        for cwd, head in ((self.base, self.head), (self.root, "HEAD")):
            result = self.call("capture", "--workspace", str(self.root), "--head", head,
                               "--output", str(self.manifest), cwd=cwd)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.manifest.exists())

    def test_stale_tracked_untracked_and_deleted_inputs_cannot_run(self):
        (self.root / "pending.txt").write_text("untracked")
        self.capture()
        for path, content in ((self.source, "changed"), (self.root / "pending.txt", "changed")):
            old = path.read_bytes()
            path.write_text(content)
            self.assertNotEqual(self.call(*self.check_args()).returncode, 0)
            self.assertFalse(self.marker.exists())
            path.write_bytes(old)
        self.source.unlink()
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)

    def test_new_untracked_file_and_head_drift_cannot_run(self):
        self.capture()
        extra = self.root / "new.txt"
        extra.write_text("new")
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)
        extra.unlink()
        self.git("commit", "--quiet", "--allow-empty", "-m", "Different candidate")
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_declared_ignored_input_is_bound(self):
        extra = self.root / "ignored.txt"
        extra.write_text("configuration")
        self.capture("--input", str(extra))
        extra.write_text("different configuration")
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_declared_input_symlink_retarget_is_bound_even_with_identical_bytes(self):
        first, second = self.base / "first.cfg", self.base / "second.cfg"
        first.write_text("same configuration")
        second.write_bytes(first.read_bytes())
        link = self.root / "ignored.txt"
        link.symlink_to(first)
        self.capture("--input", str(link))
        link.unlink()
        link.symlink_to(second)
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_declared_input_preserves_os_resolution_of_symlink_parent_dotdot(self):
        child = self.base / "target/child"
        child.mkdir(parents=True)
        actual = child.parent / "config.txt"
        actual.write_text("actual input")
        (self.base / "config.txt").write_text("decoy input")
        alias = self.base / "alias"
        alias.symlink_to(child, target_is_directory=True)
        self.capture("--input", str(alias / ".." / "config.txt"))
        actual.write_text("changed actual input")
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_manifest_and_log_tampering_and_wrong_command_are_rejected(self):
        self.capture()
        self.assertEqual(self.call(*self.check_args()).returncode, 0)
        self.assertNotEqual(self.call(*self.check_args("verify", [sys.executable, "-V"])).returncode, 0)
        self.log.write_text("different log")
        self.assertNotEqual(self.call(*self.check_args("verify")).returncode, 0)
        self.manifest.write_text(self.manifest.read_text() + "\n")
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)

    def test_input_changes_during_a_successful_command_invalidate_receipt(self):
        self.capture()
        command = [sys.executable, "-c", "from pathlib import Path; Path('source.txt').write_text('changed')"]
        result = self.call(*self.check_args(command=command))
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt["command_exit"], 0)
        self.assertIs(receipt["inputs_match"], False)
        self.assertIs(receipt["valid"], False)

    def test_failed_command_exit_and_log_are_preserved(self):
        self.capture()
        command = [sys.executable, "-c", "import sys; print('actual failure'); sys.exit(17)"]
        self.assertEqual(self.call(*self.check_args(command=command)).returncode, 17)
        self.assertEqual(json.loads(self.receipt.read_text())["command_exit"], 17)
        self.assertIn("actual failure", self.log.read_text())
        self.assertNotEqual(self.call(*self.check_args("verify", command)).returncode, 0)

    def test_missing_executable_is_not_passed(self):
        self.capture()
        self.assertNotEqual(self.call(*self.check_args(command=[str(self.base / "absent")])).returncode, 0)
        receipt = json.loads(self.receipt.read_text())
        self.assertIsNone(receipt["command_exit"])
        self.assertIs(receipt["valid"], False)

    def test_receipt_becomes_unusable_when_inputs_change_after_success(self):
        self.capture()
        self.assertEqual(self.call(*self.check_args()).returncode, 0)
        self.source.write_text("later candidate")
        self.assertNotEqual(self.call(*self.check_args("verify")).returncode, 0)

    def test_invalid_manifests_receipts_and_boolean_exit_codes_are_rejected(self):
        self.capture()
        self.assertEqual(self.call(*self.check_args()).returncode, 0)
        original = self.receipt.read_bytes()
        for invalid in ([], {**json.loads(original), "command_exit": False},
                        {**json.loads(original), "valid": 1},
                        {**json.loads(original), "process_group_stopped": "true"}):
            self.receipt.write_text(json.dumps(invalid))
            result = self.call(*self.check_args("verify"))
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
        self.manifest.write_text("[]")
        self.digest = hashlib.sha256(self.manifest.read_bytes()).hexdigest()
        result = self.call(*self.check_args())
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)

    def test_unignored_output_and_git_metadata_are_rejected_before_execution(self):
        result = self.call("capture", "--workspace", str(self.root), "--head", self.head,
                           "--output", str(self.root / "new-evidence.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "new-evidence.json").exists())
        self.capture()
        args = self.check_args()
        args[args.index("--log") + 1] = str(self.root / ".git/new-file")
        self.assertNotEqual(self.call(*args).returncode, 0)
        self.assertFalse((self.root / ".git/new-file").exists())
        self.assertFalse(self.marker.exists())

    def test_signal_termination_preserves_actual_child_exit(self):
        self.capture()
        command = [sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"]
        result = self.call(*self.check_args(command=command))
        self.assertEqual(result.returncode, 128 + signal.SIGTERM)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt["command_exit"], -signal.SIGTERM)
        self.assertIs(receipt["valid"], False)

    def test_existing_evidence_and_source_paths_are_preserved(self):
        self.capture()
        original = self.source.read_bytes()
        args = self.check_args()
        args[args.index("--log") + 1] = str(self.source)
        self.assertNotEqual(self.call(*args).returncode, 0)
        self.assertEqual(self.source.read_bytes(), original)
        self.log.write_text("prior evidence")
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)
        self.assertEqual(self.log.read_text(), "prior evidence")
        self.assertFalse(self.marker.exists())

    def test_member_directory_and_ignored_evidence_are_supported(self):
        member = self.root / "member"
        member.mkdir()
        self.manifest = self.root / ".evidence/candidate.json"
        self.log = self.root / ".evidence/check.log"
        self.receipt = self.root / ".evidence/receipt.json"
        self.capture()
        args = self.check_args()
        args[args.index("--workdir") + 1] = str(member)
        self.assertEqual(self.call(*args, cwd=member).returncode, 0)

    def test_file_symlink_target_and_mode_changes_invalidate_inputs(self):
        (self.root / "alias").symlink_to("source.txt")
        self.capture()
        self.source.chmod(self.source.stat().st_mode ^ 0o100)
        self.assertNotEqual(self.call(*self.check_args()).returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_interrupt_is_recorded_without_claiming_the_check_passed(self):
        self.capture()
        command = [sys.executable, "-u", "-c", "import time; print('ready', flush=True); time.sleep(60)"]
        process = subprocess.Popen([sys.executable, "-B", str(SCRIPT), *self.check_args(command=command)],
                                   cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if self.log.exists() and "ready" in self.log.read_text():
                    break
                time.sleep(0.02)
            else:
                self.fail("Owned check did not start")
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130, stderr)
            receipt = json.loads(self.receipt.read_text())
            self.assertIs(receipt["interrupted"], True)
            self.assertIs(receipt["valid"], False)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def check_descendant_shutdown(self, interrupt):
        self.capture()
        leader_file, child_file = self.base / "leader.pid", self.base / "child.pid"
        child = ("import os, signal, time; from pathlib import Path; "
                 "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                 + "Path(" + repr(str(child_file)) + ").write_text(str(os.getpid())); time.sleep(60)")
        leader = ("import os, subprocess, sys, time; from pathlib import Path; "
                  + "Path(" + repr(str(leader_file)) + ").write_text(str(os.getpid())); "
                  + "p = subprocess.Popen([sys.executable, '-c', " + repr(child) + "]); "
                  + "\nwhile not Path(" + repr(str(child_file)) + ").exists(): time.sleep(0.01)\n"
                  + ("p.wait()" if interrupt else "os._exit(0)"))
        command = [sys.executable, "-c", leader]
        process = subprocess.Popen([sys.executable, "-B", str(SCRIPT), *self.check_args(command=command)],
                                   cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not child_file.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(child_file.exists(), "Owned descendant did not start")
            if interrupt:
                process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 130, stderr)
            receipt = json.loads(self.receipt.read_text())
            self.assertIs(receipt["interrupted"], True)
            self.assertIs(receipt["valid"], False)
            state = subprocess.run(["ps", "-o", "stat=", "-p", child_file.read_text()],
                                   capture_output=True, text=True).stdout.strip()
            self.assertTrue(not state or state.startswith("Z"), "Descendant is still running: " + state)
        finally:
            if leader_file.exists():
                try:
                    os.killpg(int(leader_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.poll() is None:
                process.kill()
            process.communicate()

    def test_interrupt_stops_grandchild_even_after_group_leader_exits(self):
        self.check_descendant_shutdown(interrupt=True)

    def test_normal_leader_exit_does_not_leave_a_running_descendant_or_pass(self):
        self.check_descendant_shutdown(interrupt=False)


if __name__ == "__main__":
    unittest.main()

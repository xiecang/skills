"""Run with python3; all state changes stay in temporary directories."""

import json
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from budget_fixture import write_native_log


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "session_hook.py"
sys.path.insert(0, str(SCRIPT.parent))
DEFAULT_TRANSCRIPT = object()


class SessionHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orchestrator-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "项目 with spaces"
        self.root.mkdir()
        self.state_path = self.root / ".codegraph" / "agent-orchestrator.json"

    def call(self, action, sid="main-a", *extra, ok=True):
        args = [sys.executable, str(SCRIPT), action, "--root", str(self.root)]
        if action != "status":
            args += ["--session", sid]
        extra = list(extra)
        if "--resume-from" in extra and "--handoff-id" not in extra:
            state = json.loads(self.state_path.read_text())
            extra += ["--handoff-id", state.get("handoff_id", state.get("accepted_handoff_id", "missing"))]
        result = subprocess.run(args + extra, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
        return json.loads(result.stdout) if ok else result

    def hook(self, sid="main-a", cwd=None, event="SessionStart", source="compact", ok=True,
             transcript=DEFAULT_TRANSCRIPT, trigger="auto", model="gpt-6.1-sol"):
        payload = {"session_id": sid, "cwd": str(cwd or self.root),
                   "hook_event_name": event, "source": source, "trigger": trigger, "model": model}
        if transcript is DEFAULT_TRANSCRIPT:
            transcript = self.transcript(30_000, sid=sid)
        if transcript is not None:
            payload["transcript_path"] = str(transcript)
        result = subprocess.run([sys.executable, str(SCRIPT), "hook"],
                                input=json.dumps(payload), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
        return result

    def ready(self):
        self.call("activate", "main-a", "--auto-continue")
        self.hook(event="PostToolUse", transcript=self.transcript(30_000))
        handoff = self.root / ".codegraph" / "HANDOFF.md"
        handoff.write_text("Goal: continue task. Writers: stopped.\n", encoding="utf-8")
        self.call("prepare-handoff", "main-a", "--writers-stopped")
        return handoff

    def continuation(self, action, sid="main-a", *extra, ok=True):
        state = json.loads(self.state_path.read_text())
        hid = state.get("handoff_id", state.get("accepted_handoff_id", "missing"))
        return self.call(action, sid, "--handoff-id", hid, *extra, ok=ok)

    def legacy_state(self, phase="active"):
        state = self.call("status")
        state["version"] = 1
        state["phase"] = phase
        state.pop("handoff_id", None)
        state.pop("continuation", None)
        self.state_path.write_text(json.dumps(state))
        return self.state_path.read_bytes()

    def transcript(self, tokens, window=828_400, sid="main-a"):
        home = Path(self.temp.name)
        (home / "sessions").mkdir(exist_ok=True)
        path = home / "sessions" / "rollout.jsonl"
        records = [
            {"type": "session_meta", "payload": {"id": sid}},
            {"type": "turn_context", "timestamp": "2026-10-14T02:13:20Z", "payload": {
                "turn_id": "test-turn", "model": "gpt-6.1-sol"}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {
                "last_token_usage": {"total_tokens": tokens},
                "total_token_usage": {"total_tokens": 50_000_000},
                "model_context_window": window}}},
        ]
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        write_native_log(home, sid, tokens, window)
        return path

    def test_default_auto_continuation_and_explicit_manual_mode(self):
        self.assertTrue(self.call("activate")["auto_continue"])
        self.assertFalse(self.call("activate", "main-a", "--manual-continue")["auto_continue"])
        self.assertFalse(self.call("activate")["auto_continue"])
        self.assertTrue(self.call("activate", "main-a", "--auto-continue")["auto_continue"])

    def test_early_handoff_uses_current_usage_and_keeps_pending_reminder(self):
        self.call("activate")
        transcript = self.transcript(662_719)
        self.assertEqual(self.hook(event="PostToolUse", transcript=transcript).stdout, "")
        self.assertFalse(self.call("status").get("handoff_requested", False))
        transcript = self.transcript(662_720)
        result = json.loads(self.hook(event="PostToolUse", transcript=transcript).stdout)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("HANDOFF.md", result["hookSpecificOutput"]["additionalContext"])
        self.assertTrue(self.call("status")["handoff_requested"])
        repeated = json.loads(self.hook(event="PostToolUse", transcript=transcript).stdout)
        self.assertIn("交接仍待完成", repeated["hookSpecificOutput"]["additionalContext"])
        self.assertFalse((self.root / ".codegraph" / "HANDOFF.md").exists())

    def test_early_handoff_scales_down_for_smaller_windows(self):
        self.call("activate")
        transcript = self.transcript(155_999, window=256_000)
        self.assertEqual(self.hook(event="PostToolUse", transcript=transcript).stdout, "")
        transcript = self.transcript(156_000, window=256_000)
        self.assertTrue(self.hook(event="PostToolUse", transcript=transcript).stdout)

    def test_no_fixed_200k_cap_and_larger_window_scales_up(self):
        self.call("activate")
        for tokens, window in ((250_000, 828_400), (1_599_999, 2_000_000)):
            self.assertEqual(self.hook(event="PostToolUse",
                                      transcript=self.transcript(tokens, window=window)).stdout, "")
        output = self.hook(event="PostToolUse", transcript=self.transcript(1_600_000, window=2_000_000))
        self.assertIn("1600000", output.stdout)
        self.assertIn("400000", output.stdout)

    def test_verified_compaction_limit_reduces_budget(self):
        self.call("activate", "main-a", "--compact-limit", "500000", "--compact-model", "gpt-6.1-sol")
        self.assertEqual(self.hook(event="PostToolUse", transcript=self.transcript(399_999)).stdout, "")
        output = self.hook(event="PostToolUse", transcript=self.transcript(400_000))
        self.assertIn("400000", output.stdout)
        self.assertIn("预算 500000", output.stdout)
        self.assertIn("预留 100000", output.stdout)

    def test_verified_780k_target_hands_off_at_624k(self):
        self.call("activate", "main-a", "--compact-limit", "780000", "--compact-model", "gpt-6.1-sol")
        self.assertEqual(self.hook(event="PostToolUse", transcript=self.transcript(623_999)).stdout, "")
        output = self.hook(event="PostToolUse", transcript=self.transcript(624_000))
        self.assertIn("提前交接线 624000", output.stdout)
        self.assertIn("预算 780000", output.stdout)
        self.assertIn("预留 156000", output.stdout)

    def test_verified_limit_never_expands_reported_window(self):
        self.call("activate", "main-a", "--compact-limit", "900000", "--compact-model", "gpt-6.1-sol")
        self.assertEqual(self.hook(event="PostToolUse", transcript=self.transcript(662_719)).stdout, "")
        output = self.hook(event="PostToolUse", transcript=self.transcript(662_720))
        self.assertIn("预算 828400", output.stdout)
        self.assertIn("预留 165680", output.stdout)

    def test_compaction_limit_is_ignored_after_model_change(self):
        self.call("activate", "main-a", "--compact-limit", "500000", "--compact-model", "gpt-6.1-sol")
        for model in ("gpt-6-astra", None):
            self.assertIn("预算未核实", self.hook(event="PostToolUse",
                          transcript=self.transcript(400_000), model=model).stdout)
        self.assertFalse(self.call("status").get("handoff_requested", False))

    def test_missing_window_does_not_guess_or_trigger_creation(self):
        self.call("activate")
        output = self.hook(event="PostToolUse", transcript=self.transcript(700_000, window=None))
        self.assertIn("窗口未知", output.stdout)
        self.assertFalse(self.call("status").get("handoff_requested", False))

    def test_insufficient_budget_reports_without_starting_handoff_loop(self):
        self.call("activate")
        for window in (64_000, 100_000):
            output = self.hook(event="PostToolUse", transcript=self.transcript(40_000, window=window))
            self.assertIn("预算不足", output.stdout)
            self.assertFalse(self.call("status").get("handoff_requested", False))
            compact = self.hook(event="SessionStart", source="compact",
                                transcript=self.transcript(40_000, window=window))
            self.assertIn("预算不足", compact.stdout)
            self.assertFalse(self.call("status").get("handoff_requested", False))

    def test_budget_recovery_clears_handoff_guard_only_after_valid_window(self):
        self.call("activate")
        self.hook(event="PostToolUse", transcript=self.transcript(40_000, window=64_000))
        self.assertTrue(self.call("status")["handoff_budget_blocked"])
        self.hook(event="PostToolUse", transcript=self.transcript(40_000, window=None))
        self.assertTrue(self.call("status")["handoff_budget_blocked"])
        self.assertEqual(self.hook(event="PostToolUse", transcript=self.transcript(40_000)).stdout, "")
        self.assertFalse(self.call("status").get("handoff_budget_blocked", False))
        self.hook(source="compact")
        self.assertTrue(self.call("status")["handoff_requested"])

    def test_compaction_and_budget_checks_cannot_set_contradictory_flags(self):
        self.call("activate")
        self.hook(event="PostToolUse", transcript=self.transcript(30_000))
        spec = importlib.util.spec_from_file_location("hook_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = module.project_root(self.root)
        original = module.set_budget_blocked

        def compact_before_budget_update(root, sid, blocked, **kwargs):
            self.assertIsNotNone(module.request_handoff(root, sid))
            return original(root, sid, blocked, **kwargs)

        event = {"session_id": "main-a", "cwd": str(root), "hook_event_name": "PostToolUse",
                 "model": "gpt-6.1-sol", "transcript_path": str(self.transcript(40_000, window=64_000))}
        with patch.object(module, "set_budget_blocked", side_effect=compact_before_budget_update):
            self.assertIsNone(module.hook_output(event))
        state = self.call("status")
        self.assertTrue(state["handoff_requested"])
        self.assertFalse(state.get("handoff_budget_blocked", False))

        self.call("deactivate")
        self.call("activate")
        self.assertIsNotNone(original(root, "main-a", True))
        self.assertIsNone(module.request_handoff(root, "main-a"))
        state = self.call("status")
        self.assertTrue(state["handoff_budget_blocked"])
        self.assertFalse(state.get("handoff_requested", False))

    def test_fractional_reserve_rounds_up_not_beyond_budget(self):
        self.call("activate")
        self.assertEqual(self.hook(event="PostToolUse",
                                  transcript=self.transcript(662_719, window=828_401)).stdout, "")
        output = self.hook(event="PostToolUse", transcript=self.transcript(662_720, window=828_401))
        self.assertIn("预留 165681", output.stdout)

    def take_over(self):
        self.ready()
        return self.call("activate", "main-b", "--resume-from", "main-a")

    def test_small_window_successor_cannot_repeat_automatic_handoff(self):
        state = self.take_over()
        self.assertFalse(state["startup_budget_checked"])
        transcript = self.transcript(30_000, window=128_000, sid="main-b")
        for _ in range(2):
            self.assertIn("启动余量不足", self.hook("main-b", event="PostToolUse", transcript=transcript).stdout)
        state = self.call("status")
        self.assertTrue(state["startup_budget_checked"])
        self.assertTrue(state["handoff_budget_blocked"])
        self.assertFalse(state.get("handoff_requested", False))
        self.call("prepare-handoff", "main-b", "--writers-stopped")
        self.continuation("begin-continuation", "main-b", ok=False)
        before = self.state_path.read_bytes()
        self.assertIn("不自动创建聊天", self.hook("main-b", source="resume", transcript=transcript).stdout)
        self.assertEqual(before, self.state_path.read_bytes())

    def test_successor_startup_margin_boundary_and_recovery(self):
        self.take_over()
        transcript = self.transcript(13_000, window=128_000, sid="main-b")
        self.assertIn("启动余量不足", self.hook("main-b", event="PostToolUse", transcript=transcript).stdout)
        self.assertTrue(self.call("status")["handoff_budget_blocked"])
        transcript = self.transcript(12_999, window=128_000, sid="main-b")
        self.assertEqual(self.hook("main-b", event="PostToolUse", transcript=transcript).stdout, "")
        self.assertFalse(self.call("status").get("handoff_budget_blocked", False))
        transcript = self.transcript(28_000, window=128_000, sid="main-b")
        self.assertIn("提前交接线", self.hook("main-b", event="PostToolUse", transcript=transcript).stdout)

    def test_successor_budget_recovers_after_larger_window(self):
        self.take_over()
        self.hook("main-b", event="PostToolUse", transcript=self.transcript(30_000, window=128_000, sid="main-b"))
        for tokens, window in ((30_000, None), (0, 828_400)):
            self.hook("main-b", event="PostToolUse", transcript=self.transcript(tokens, window=window, sid="main-b"))
            self.assertTrue(self.call("status")["handoff_budget_blocked"])
        self.assertEqual(self.hook("main-b", event="PostToolUse",
                                  transcript=self.transcript(30_000, sid="main-b")).stdout, "")
        self.assertFalse(self.call("status").get("handoff_budget_blocked", False))

    def test_successor_first_count_just_above_minimum_margin_can_continue(self):
        self.take_over()
        output = self.hook("main-b", event="PostToolUse",
                           transcript=self.transcript(12_999, window=128_000, sid="main-b"))
        self.assertEqual(output.stdout, "")
        state = self.call("status")
        self.assertTrue(state["startup_budget_checked"])
        self.assertFalse(state.get("handoff_budget_blocked", False))
        self.assertFalse(state.get("handoff_requested", False))

    def test_successor_unknown_or_zero_usage_does_not_finish_startup_check(self):
        self.take_over()
        for event in ("PostToolUse", "SessionStart"):
            for tokens, window in ((30_000, None), (0, 828_400)):
                self.hook("main-b", event=event, transcript=self.transcript(tokens, window=window, sid="main-b"))
                state = self.call("status")
                self.assertFalse(state["startup_budget_checked"])
                self.assertFalse(state.get("handoff_requested", False))
        self.call("prepare-handoff", "main-b", "--writers-stopped")
        self.continuation("begin-continuation", "main-b", ok=False)

    def test_compaction_cannot_bypass_successor_startup_guard(self):
        self.take_over()
        transcript = self.transcript(30_000, window=128_000, sid="main-b")
        for source in ("compact", "resume", "compact"):
            self.hook("main-b", source=source, transcript=transcript)
            self.assertFalse(self.call("status").get("handoff_requested", False))
        self.assertTrue(self.call("status")["handoff_budget_blocked"])
        output = self.hook("main-b", source="compact", transcript=self.transcript(10_000, window=128_000, sid="main-b"))
        self.assertIn("恢复交接", output.stdout)
        self.assertTrue(self.call("status")["handoff_requested"])

    def test_large_window_successor_keeps_existing_threshold(self):
        self.take_over()
        self.call("activate", "main-b", "--compact-limit", "780000", "--compact-model", "gpt-6.1-sol")
        self.assertEqual(self.hook("main-b", event="PostToolUse", transcript=self.transcript(30_000, sid="main-b")).stdout, "")
        self.assertTrue(self.call("status")["startup_budget_checked"])
        self.assertIn("提前交接线 624000", self.hook("main-b", event="PostToolUse",
                      transcript=self.transcript(624_000, sid="main-b")).stdout)

    def test_legacy_active_successor_is_not_reclassified_as_starting(self):
        self.take_over()
        state = self.call("status")
        state.pop("startup_budget_checked")
        self.state_path.write_text(json.dumps(state))
        before = self.state_path.read_bytes()
        self.call("status")
        self.assertEqual(before, self.state_path.read_bytes())
        output = self.hook("main-b", event="PostToolUse", transcript=self.transcript(30_000, window=128_000, sid="main-b"))
        self.assertIn("提前交接线", output.stdout)
        self.assertNotIn("startup_budget_checked", self.call("status"))

    def test_startup_check_survives_retry_and_resets_only_for_next_successor(self):
        self.take_over()
        self.hook("main-b", event="PostToolUse", transcript=self.transcript(30_000, sid="main-b"))
        state = self.call("status")
        self.assertEqual(state, self.call("activate", "main-b", "--resume-from", "main-a"))
        self.call("prepare-handoff", "main-b", "--writers-stopped")
        self.assertTrue(self.continuation("begin-continuation", "main-b")["create_allowed"])
        state = self.call("activate", "main-c", "--resume-from", "main-b")
        self.assertFalse(state["startup_budget_checked"])

    def test_concurrent_first_usage_checks_preserve_guard_and_owner(self):
        self.take_over()
        payload = {"session_id": "main-b", "cwd": str(self.root), "hook_event_name": "PostToolUse",
                   "model": "gpt-6.1-sol", "transcript_path": str(self.transcript(30_000, window=128_000, sid="main-b"))}
        processes = [subprocess.Popen([sys.executable, str(SCRIPT), "hook"], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        for process in processes:
            process.stdin.write(json.dumps(payload))
            process.stdin.close()
            process.stdin = None
        for process in processes:
            process.communicate(timeout=10)
        self.assertIn(0, [p.returncode for p in processes])
        self.assertTrue(all(p.returncode in (0, 1) for p in processes))
        state = self.call("status")
        self.assertEqual(state["session_id"], "main-b")
        self.assertTrue(state["startup_budget_checked"])
        self.assertTrue(state["handoff_budget_blocked"])
        self.assertFalse(state.get("handoff_requested", False))

    def test_invalid_startup_marker_is_preserved(self):
        self.take_over()
        state = self.call("status")
        state["startup_budget_checked"] = 1
        self.state_path.write_text(json.dumps(state))
        before = self.state_path.read_bytes()
        self.call("status", ok=False)
        self.assertEqual(before, self.state_path.read_bytes())

    def test_concurrent_compaction_setting_change_does_not_accept_stale_startup_budget(self):
        self.take_over()
        spec = importlib.util.spec_from_file_location("hook_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = module.project_root(self.root)
        original = module.set_budget_blocked

        def lower_budget_before_update(root, sid, blocked, **kwargs):
            module.transition(root, sid, "activate", compact_limit=128_000, compact_model="gpt-6.1-sol")
            return original(root, sid, blocked, **kwargs)

        event = {"session_id": "main-b", "cwd": str(root), "hook_event_name": "PostToolUse",
                 "model": "gpt-6.1-sol", "transcript_path": str(self.transcript(30_000, sid="main-b"))}
        with patch.object(module, "set_budget_blocked", side_effect=lower_budget_before_update):
            self.assertIsNone(module.hook_output(event))
        state = self.call("status")
        self.assertFalse(state["startup_budget_checked"])
        self.assertFalse(state.get("handoff_requested", False))
        self.assertIsNotNone(module.hook_output(event))
        self.assertTrue(self.call("status")["handoff_budget_blocked"])
        self.call("prepare-handoff", "main-b", "--writers-stopped")
        self.continuation("begin-continuation", "main-b", ok=False)

    def test_compaction_budget_requires_valid_paired_owner_settings(self):
        self.call("activate")
        before = self.state_path.read_bytes()
        for flags in (("--compact-limit", "500000"), ("--compact-model", "gpt-6.1-sol"),
                      ("--compact-limit", "0", "--compact-model", "gpt-6.1-sol"),
                      ("--compact-limit", "-1", "--compact-model", "gpt-6.1-sol")):
            self.call("activate", "main-a", *flags, ok=False)
            self.assertEqual(self.state_path.read_bytes(), before)
        self.call("activate", "other", "--compact-limit", "500000",
                  "--compact-model", "gpt-6.1-sol", ok=False)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_compaction_budget_survives_owner_retry_but_not_successor(self):
        self.call("activate", "main-a", "--compact-limit", "500000", "--compact-model", "gpt-6.1-sol")
        state = self.call("activate")
        self.assertEqual(state["compaction_budget"], {"limit": 500000, "model": "gpt-6.1-sol"})
        self.ready()
        successor = self.call("activate", "main-b", "--resume-from", "main-a")
        self.assertNotIn("compaction_budget", successor)
        state = self.call("activate", "main-b", "--resume-from", "main-a", "--compact-limit", "600000",
                          "--compact-model", "gpt-6.1-sol")
        self.assertEqual(state["compaction_budget"]["limit"], 600000)

    def test_malformed_compaction_budget_is_preserved(self):
        self.call("activate")
        state = self.call("status")
        state["compaction_budget"] = {"limit": True, "model": "gpt-6.1-sol"}
        self.state_path.write_text(json.dumps(state))
        before = self.state_path.read_bytes()
        self.call("status", ok=False)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_early_handoff_preserves_manual_continuation_choice(self):
        self.call("activate", "main-a", "--manual-continue")
        transcript = self.transcript(662_720)
        context = json.loads(self.hook(event="PostToolUse", transcript=transcript).stdout)
        self.assertIn("手动接续", context["hookSpecificOutput"]["additionalContext"])
        self.assertFalse(self.call("status")["auto_continue"])

    def test_native_counter_triggers_handoff_when_api_reports_only_419k(self):
        self.call("activate")
        transcript = self.transcript(419_131)
        write_native_log(Path(self.temp.name), "main-a", 778_590, limit=780_000)
        result = self.hook(event="PostToolUse", transcript=transcript)
        self.assertIn("提前交接线 624000", result.stdout)
        evidence = self.call("status")["budget_evidence"]
        self.assertEqual(evidence["tokens"], 778_590)
        self.assertEqual(evidence["api_tokens"], 419_131)
        self.assertEqual(evidence["limit"], 780_000)
        self.assertTrue(self.call("status")["handoff_requested"])

    def test_missing_native_log_cannot_complete_startup_or_grant_creation(self):
        self.call("activate")
        transcript = self.transcript(700_000)
        (Path(self.temp.name) / "logs_2.sqlite").unlink()
        self.assertIn("预算未核实", self.hook(event="PostToolUse", transcript=transcript).stdout)
        state = self.call("status")
        self.assertFalse(state["startup_budget_checked"])
        self.assertFalse(state["budget_evidence"]["verified"])
        self.assertFalse(state.get("handoff_requested", False))
        (self.root / ".codegraph" / "HANDOFF.md").write_text("Manual recovery.\n")
        self.call("prepare-handoff", "main-a", "--writers-stopped")
        self.continuation("begin-continuation", ok=False)

    def test_unknown_budget_after_positive_check_still_blocks_creation(self):
        self.ready()
        state = self.call("status")
        state["budget_evidence"] = {"verified": False}
        self.state_path.write_text(json.dumps(state))
        self.continuation("begin-continuation", ok=False)

    def test_inactive_chat_reactivation_checks_existing_native_context(self):
        self.call("activate")
        self.hook(event="PostToolUse", transcript=self.transcript(30_000))
        self.call("deactivate")
        self.assertFalse(self.call("activate")["startup_budget_checked"])
        transcript = self.transcript(319_000)
        write_native_log(Path(self.temp.name), "main-a", 625_000, limit=780_000)
        self.assertIn("提前交接线 624000", self.hook(source="resume", transcript=transcript).stdout)
        self.assertTrue(self.call("status")["startup_budget_checked"])

    def test_user_prompt_checks_native_budget_and_check_command_uses_same_path(self):
        self.call("activate")
        transcript = self.transcript(5_000)
        write_native_log(Path(self.temp.name), "main-a", 650_000, limit=780_000)
        self.assertIn("提前交接线", self.hook(event="UserPromptSubmit", transcript=transcript).stdout)
        result = self.call("check-budget", "main-a", "--transcript-path", str(transcript),
                           "--model", "gpt-6.1-sol")
        self.assertIn("交接仍待完成", result["hookSpecificOutput"]["additionalContext"])

    def test_precompact_observation_reports_actual_counters_without_requesting_handoff(self):
        self.call("activate")
        transcript = self.transcript(419_131)
        write_native_log(Path(self.temp.name), "main-a", 780_878, limit=780_000)
        before = self.state_path.read_bytes()
        output = json.loads(self.hook(event="PreCompact", transcript=transcript).stdout)
        self.assertIn("原生计数 780878", output["systemMessage"])
        self.assertIn("API 单次用量 419131", output["systemMessage"])
        self.assertNotIn("continue", output)
        self.assertEqual(self.state_path.read_bytes(), before)
        self.hook(event="PostToolUse", transcript=transcript)
        before = self.state_path.read_bytes()
        output = json.loads(self.hook(event="PreCompact", transcript=transcript).stdout)
        self.assertIn("原生计数 780878", output["systemMessage"])
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_precompact_observes_without_blocking_or_changing_owner_state(self):
        transcript = self.transcript(10)
        self.assertEqual(self.hook(event="PreCompact", transcript=transcript).stdout, "")
        self.call("activate")
        before = self.state_path.read_bytes()
        output = json.loads(self.hook(event="PreCompact", transcript=transcript).stdout)
        self.assertIn("systemMessage", output)
        self.assertNotIn("continue", output)
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertIn("manual", self.hook(event="PreCompact", transcript=transcript, trigger="manual").stdout)
        self.call("deactivate")
        self.assertEqual(self.hook(event="PreCompact", transcript=transcript).stdout, "")

    def test_subagents_sharing_parent_session_id_and_directory_are_untouched(self):
        self.call("activate")
        transcript = self.transcript(700_000, sid="child-agent")
        before = self.state_path.read_bytes()
        for event in ("SessionStart", "PostToolUse", "PreCompact"):
            self.assertEqual(self.hook(event=event, transcript=transcript).stdout, "")
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_missing_transcript_does_not_interfere_with_unverified_actor(self):
        self.call("activate")
        for event in ("SessionStart", "PostToolUse", "PreCompact"):
            self.assertEqual(self.hook(event=event, transcript=None).stdout, "")

    def test_partial_final_log_record_preserves_last_valid_usage(self):
        self.call("activate")
        transcript = self.transcript(662_720)
        with transcript.open("a") as stream:
            stream.write('{"type": "event_msg", "payload":')
        self.assertTrue(self.hook(event="PostToolUse", transcript=transcript).stdout)

    def test_recovery_does_not_parse_body_of_large_or_damaged_log(self):
        self.call("activate")
        self.hook(event="PostToolUse", transcript=self.transcript(30_000))
        transcript = self.transcript(10)
        with transcript.open("a") as stream:
            stream.write("damaged log record\n")
        self.hook(event="PostToolUse", transcript=transcript, ok=False)
        self.assertTrue(self.hook(event="SessionStart", transcript=transcript).stdout)
        self.assertTrue(self.hook(event="PostToolUse", transcript=transcript).stdout)

    def test_invalid_usage_does_not_mark_handoff_or_expose_log_content(self):
        self.call("activate")
        transcript = self.transcript("invalid")
        result = self.hook(event="PostToolUse", transcript=transcript, ok=False)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.call("status").get("handoff_requested", False))

    def test_manual_choice_survives_handoff_and_successor_retry(self):
        self.call("activate", "main-a", "--manual-continue")
        (self.root / ".codegraph" / "HANDOFF.md").write_text("Continue current task.\n")
        self.call("prepare-handoff", "main-a", "--writers-stopped")
        first = self.call("activate", "main-b", "--resume-from", "main-a")
        self.assertFalse(first["auto_continue"])
        self.assertEqual(first, self.call("activate", "main-b", "--resume-from", "main-a"))

    def test_requested_handoff_state_is_not_inherited_by_successor(self):
        self.call("activate")
        self.hook(event="PostToolUse", transcript=self.transcript(662_720))
        (self.root / ".codegraph" / "HANDOFF.md").write_text("Continue current task.\n")
        self.call("prepare-handoff", "main-a", "--writers-stopped")
        state = self.call("activate", "main-b", "--resume-from", "main-a")
        self.assertFalse(state.get("handoff_requested", False))

    def test_explicit_manual_choice_overrides_auto_mode_during_takeover_and_retry(self):
        self.ready()
        state = self.call("activate", "main-b", "--resume-from", "main-a", "--manual-continue")
        self.assertFalse(state["auto_continue"])
        self.assertEqual(state, self.call("activate", "main-b", "--resume-from", "main-a"))
        self.assertTrue(self.call("activate", "main-b", "--resume-from", "main-a", "--auto-continue")["auto_continue"])
        self.assertFalse(self.call("activate", "main-b", "--resume-from", "main-a", "--manual-continue")["auto_continue"])

    def test_unregistered_hook_is_silent_and_creates_nothing(self):
        self.assertEqual(self.hook().stdout, "")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_only_registered_session_gets_context(self):
        self.call("activate", "main-a", "--auto-continue")
        self.assertEqual(self.hook(sid="ordinary-session").stdout, "")
        output = json.loads(self.hook().stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        self.assertIn("HANDOFF.md", output["additionalContext"])

    def test_nested_directory_resolves_main_workspace(self):
        self.call("activate")
        nested = self.root / "src" / "nested"
        nested.mkdir(parents=True)
        self.assertTrue(self.hook(cwd=nested).stdout)

    def test_other_events_and_subagent_events_are_silent(self):
        self.call("activate")
        self.assertEqual(self.hook(source="startup").stdout, "")
        self.assertEqual(self.hook(event="SubagentStart").stdout, "")
        self.assertEqual(self.hook(event="PostCompact").stdout, "")

    def test_deactivation_silences_hook_and_allows_next_task(self):
        self.call("activate")
        self.call("deactivate", "other-session", ok=False)
        self.assertEqual(self.call("deactivate")["phase"], "inactive")
        self.assertEqual(self.hook().stdout, "")
        self.assertEqual(self.call("activate", "next-task")["session_id"], "next-task")

    def test_existing_owner_and_user_documents_are_preserved(self):
        directory = self.root / ".codegraph"
        directory.mkdir()
        plan = directory / "plan.md"
        plan.write_text("User plan, leave unchanged.", encoding="utf-8")
        self.call("activate")
        before = self.state_path.read_bytes()
        self.call("activate", "other-session", ok=False)
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertEqual(plan.read_text(), "User plan, leave unchanged.")

    def test_repeated_activation_preserves_and_can_record_authorization(self):
        self.call("activate")
        self.assertTrue(self.call("activate", "main-a", "--auto-continue")["auto_continue"])
        self.assertTrue(self.call("activate")["auto_continue"])

    def test_release_requires_document_and_writer_acknowledgement(self):
        self.call("activate")
        self.call("prepare-handoff", ok=False)
        self.call("prepare-handoff", "main-a", "--writers-stopped", ok=False)
        (self.root / ".codegraph" / "HANDOFF.md").write_text(" ", encoding="utf-8")
        self.call("prepare-handoff", "main-a", "--writers-stopped", ok=False)
        self.assertEqual(self.call("status")["phase"], "active")

    def test_handoff_has_one_owner_and_old_owner_cannot_clear_successor(self):
        self.ready()
        self.assertIn("旧主会话已释放", self.hook().stdout)
        self.call("activate", "main-a", ok=False)
        self.call("activate", "main-a", "--resume-from", "main-a", ok=False)
        self.call("activate", "main-b", "--resume-from", "wrong-source", ok=False)
        state = self.call("activate", "main-b", "--resume-from", "main-a")
        self.assertTrue(state["auto_continue"])
        self.call("activate", "main-c", "--resume-from", "main-a", ok=False)
        self.call("deactivate", "main-a", ok=False)
        self.assertEqual(self.call("status")["session_id"], "main-b")

    def test_changed_handoff_cannot_be_claimed(self):
        handoff = self.ready()
        handoff.write_text("Changed after release.", encoding="utf-8")
        self.call("activate", "main-b", "--resume-from", "main-a", ok=False)
        self.assertEqual(self.call("status")["phase"], "ready")

    def test_same_successor_can_retry_after_uncertain_command_result(self):
        self.ready()
        first = self.call("activate", "main-b", "--resume-from", "main-a")
        retry = self.call("activate", "main-b", "--resume-from", "main-a")
        self.assertEqual(first, retry)

    def test_commands_require_explicit_id_when_runtime_id_is_missing(self):
        import os
        environment = dict(os.environ)
        environment.pop("CODEX_THREAD_ID", None)
        result = subprocess.run([sys.executable, str(SCRIPT), "activate", "--root", str(self.root)],
                                env=environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.state_path.exists())
        self.call("activate", "verified-main")

    def test_concurrent_successors_cannot_both_claim(self):
        self.ready()
        hid = self.call("status")["handoff_id"]
        processes = [subprocess.Popen(
            [sys.executable, str(SCRIPT), "activate", "--root", str(self.root),
             "--session", sid, "--resume-from", "main-a", "--handoff-id",
             hid],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for sid in ("main-b", "main-c")]
        for process in processes:
            process.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 1])
        self.assertIn(self.call("status")["session_id"], {"main-b", "main-c"})

    def test_corrupt_state_is_not_overwritten_or_silently_accepted(self):
        self.state_path.parent.mkdir()
        self.state_path.write_text("not json", encoding="utf-8")
        self.call("activate", ok=False)
        self.hook(ok=False)
        self.assertEqual(self.state_path.read_text(), "not json")

    def test_symlink_state_is_not_followed(self):
        self.state_path.parent.mkdir()
        target = Path(self.temp.name) / "unrelated.json"
        target.write_text("Keep this file", encoding="utf-8")
        self.state_path.symlink_to(target)
        self.call("activate", ok=False)
        self.assertEqual(target.read_text(), "Keep this file")

    def test_configuration_command_handles_spaces_quotes_and_unicode(self):
        installed = Path(self.temp.name) / "安装 skill's $path"
        installed.mkdir()
        copied = installed / SCRIPT.name
        shutil.copy2(SCRIPT, copied)
        shutil.copy2(SCRIPT.parent / "context_budget.py", installed / "context_budget.py")
        config = subprocess.run([sys.executable, str(copied), "config"],
                                text=True, capture_output=True, check=True).stdout
        self.assertIn("PreCompact", config)
        self.assertIn("UserPromptSubmit", config)
        self.assertIn("^(startup|compact|resume)$", config)
        self.assertEqual(config.count("statusMessage = "), 4)
        label = next(line for line in config.splitlines() if line.startswith("statusMessage = "))
        self.assertIn("agent-orchestrator", json.loads(label.split(" = ", 1)[1]))
        line = next(line for line in config.splitlines() if line.startswith("command = "))
        command = json.loads(line.split(" = ", 1)[1])
        payload = {"session_id": "main-a", "cwd": str(self.root),
                   "hook_event_name": "SessionStart", "source": "compact"}
        result = subprocess.run(command, shell=True, input=json.dumps(payload),
                                text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_invalid_hook_payload_fails_with_diagnostic(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "hook"], input="not json",
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("agent-orchestrator:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_resume_recovers_pending_but_leaves_normal_work_alone(self):
        self.call("activate")
        self.assertEqual(self.hook(source="resume").stdout, "")
        self.hook(event="PostToolUse", transcript=self.transcript(662_720))
        self.assertIn("交接仍待完成", self.hook(source="resume").stdout)

    def test_ready_recovers_without_rewriting_handoff_or_state(self):
        handoff = self.ready()
        before = self.state_path.read_bytes(), handoff.read_bytes()
        for source in ("compact", "resume"):
            self.assertIn("只核对创建和接管结果", self.hook(source=source).stdout)
        self.assertIn("旧主会话已释放", self.hook(event="PostToolUse").stdout)
        self.assertEqual(before, (self.state_path.read_bytes(), handoff.read_bytes()))

    def test_legacy_ready_recovery_is_read_only_and_unknown(self):
        self.ready()
        before = self.legacy_state("ready")
        self.assertIn("创建阶段=unknown", self.hook().stdout)
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertEqual(self.call("status")["version"], 1)

    def test_v1_ready_ignores_untrusted_v2_extension_fields(self):
        self.ready()
        self.legacy_state("ready")
        state = self.call("status")
        state.update(handoff_id="invalid", continuation=[])
        self.state_path.write_text(json.dumps(state))
        before = self.state_path.read_bytes()
        self.assertIn("创建阶段=unknown", self.hook().stdout)
        self.assertEqual(self.state_path.read_bytes(), before)
        upgraded = self.call("prepare-handoff", "main-a", "--writers-stopped")
        self.assertNotEqual(upgraded["handoff_id"], "invalid")
        self.assertEqual(upgraded["continuation"]["status"], "unknown")

    def test_creation_permit_is_issued_once_and_survives_prepare_retry(self):
        self.ready()
        first = self.continuation("begin-continuation")
        self.assertTrue(first["create_allowed"])
        self.assertEqual(first["state"]["continuation"]["status"], "creating")
        second = self.continuation("begin-continuation")
        self.assertFalse(second["create_allowed"])
        self.assertEqual(first["state"], second["state"])
        self.call("prepare-handoff", "main-a", "--writers-stopped")
        self.assertFalse(self.continuation("begin-continuation")["create_allowed"])

    def test_concurrent_creation_requests_issue_at_most_one_permit(self):
        self.ready()
        hid = self.call("status")["handoff_id"]
        args = [sys.executable, str(SCRIPT), "begin-continuation", "--root", str(self.root),
                "--session", "main-a", "--handoff-id", hid]
        processes = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True) for _ in range(2)]
        results = [p.communicate(timeout=10) for p in processes]
        permissions = [json.loads(out)["create_allowed"] for p, (out, err) in zip(processes, results)
                       if p.returncode == 0]
        self.assertEqual(permissions.count(True), 1)
        self.assertTrue(all(p.returncode in (0, 1) for p in processes))
        self.assertFalse(self.continuation("begin-continuation")["create_allowed"])

    def test_manual_mode_never_grants_creation_permit(self):
        self.call("activate", "main-a", "--manual-continue")
        (self.root / ".codegraph" / "HANDOFF.md").write_text("Manual handoff.\n")
        self.call("prepare-handoff", "main-a", "--writers-stopped")
        self.continuation("begin-continuation", ok=False)
        self.assertIn("手动接续，不自动创建聊天", self.hook().stdout)

    def test_unknown_and_failed_creation_never_reissue_permit(self):
        self.ready()
        self.continuation("begin-continuation")
        for result in ("unknown", "failed"):
            state = self.continuation("record-continuation", "main-a", "--result", result)
            self.assertEqual(state["continuation"]["status"], result)
            self.assertFalse(self.continuation("begin-continuation")["create_allowed"])

    def test_created_receipt_binds_successor_and_cannot_be_downgraded(self):
        self.ready()
        self.continuation("begin-continuation")
        first = self.continuation("record-continuation", "main-a", "--result", "created",
                                  "--thread-id", "main-b")
        self.assertEqual(first["phase"], "ready")
        self.assertEqual(first, self.continuation("record-continuation", "main-a", "--result", "unknown"))
        self.continuation("record-continuation", "main-a", "--result", "created",
                          "--thread-id", "main-c", ok=False)
        self.call("activate", "main-c", "--resume-from", "main-a", ok=False)
        self.call("activate", "main-b", "--resume-from", "main-a")

    def test_receipt_requires_attempt_and_valid_thread(self):
        self.ready()
        self.continuation("record-continuation", "main-a", "--result", "unknown", ok=False)
        self.continuation("begin-continuation")
        self.continuation("record-continuation", "main-a", "--result", "created", ok=False)
        self.continuation("record-continuation", "main-a", "--result", "created",
                          "--thread-id", "main-a", ok=False)
        self.continuation("record-continuation", "main-a", "--result", "unknown",
                          "--thread-id", "main-b", ok=False)

    def test_takeover_before_receipt_does_not_overwrite_new_owner(self):
        self.ready()
        self.continuation("begin-continuation")
        claimed = self.call("activate", "main-b", "--resume-from", "main-a")
        before = self.state_path.read_bytes()
        for result in ("unknown", "failed", "created"):
            extra = ("--thread-id", "main-b") if result == "created" else ()
            self.assertEqual(claimed, self.continuation("record-continuation", "main-a",
                                                       "--result", result, *extra))
        self.assertEqual(self.state_path.read_bytes(), before)
        self.continuation("record-continuation", "main-a", "--result", "created",
                          "--thread-id", "main-c", ok=False)
        self.assertIn("新主会话已接管", self.hook(source="resume").stdout)

    def test_wrong_handoff_id_never_changes_state(self):
        self.ready()
        before = self.state_path.read_bytes()
        for action in ("begin-continuation", "record-continuation", "activate"):
            extra = ("--result", "unknown") if action == "record-continuation" else ()
            if action == "activate":
                extra = ("--resume-from", "main-a")
            self.call(action, "main-b" if action == "activate" else "main-a",
                      "--handoff-id", str(uuid.uuid4()), *extra, ok=False)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_takeover_requires_handoff_id_even_when_source_matches(self):
        self.ready()
        result = subprocess.run([sys.executable, str(SCRIPT), "activate", "--root", str(self.root),
                                 "--session", "main-b", "--resume-from", "main-a"],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.call("status")["phase"], "ready")

    def test_handoff_digest_checked_before_creation_and_receipt(self):
        handoff = self.ready()
        handoff.write_text("Changed.\n")
        before = self.state_path.read_bytes()
        self.continuation("begin-continuation", ok=False)
        self.continuation("record-continuation", "main-a", "--result", "unknown", ok=False)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_ready_cannot_be_deactivated_to_clear_creation_history(self):
        self.ready()
        self.call("deactivate", ok=False)
        self.assertEqual(self.call("status")["phase"], "ready")

    def test_new_handoff_gets_new_id_and_late_receipt_preserves_it(self):
        self.ready()
        old = self.call("status")["handoff_id"]
        self.call("activate", "main-b", "--resume-from", "main-a")
        (self.root / ".codegraph" / "HANDOFF.md").write_text("Next handoff.\n")
        state = self.call("prepare-handoff", "main-b", "--writers-stopped")
        self.assertNotEqual(state["handoff_id"], old)
        self.assertEqual(state["continuation"]["status"], "not_started")
        receipt = self.call("record-continuation", "main-a", "--handoff-id", old,
                            "--result", "created", "--thread-id", "main-b")
        self.assertEqual(receipt, state)

    def test_v1_active_upgrade_requires_owner_and_preserves_mode(self):
        self.call("activate", "main-a", "--manual-continue")
        before = self.legacy_state()
        self.call("activate", "main-b", ok=False)
        self.assertEqual(before, self.state_path.read_bytes())
        state = self.call("activate")
        self.assertEqual(state["version"], 2)
        self.assertFalse(state["auto_continue"])

    def test_v1_ready_upgrade_marks_creation_unknown_and_preserves_digest(self):
        self.ready()
        digest = self.call("status")["handoff_sha256"]
        before = self.legacy_state("ready")
        self.call("prepare-handoff", "main-b", "--writers-stopped", ok=False)
        self.assertEqual(self.state_path.read_bytes(), before)
        state = self.call("prepare-handoff", "main-a", "--writers-stopped")
        self.assertEqual(state["version"], 2)
        self.assertEqual(state["continuation"]["status"], "unknown")
        self.assertEqual(state["handoff_sha256"], digest)
        self.assertFalse(self.continuation("begin-continuation")["create_allowed"])
        state = self.continuation("record-continuation", "main-a", "--result", "created",
                                  "--thread-id", "main-b")
        self.assertEqual(state["continuation"]["thread_id"], "main-b")
        self.call("activate", "main-b", "--resume-from", "main-a")

    def test_malformed_v2_creation_state_is_preserved(self):
        self.ready()
        state = self.call("status")
        for creation in ({"status": "created"}, {"status": []}, [], {"status": "invalid"}):
            with self.subTest(creation=creation):
                state["continuation"] = creation
                self.state_path.write_text(json.dumps(state))
                before = self.state_path.read_bytes()
                result = self.call("status", ok=False)
                self.assertNotIn("Traceback", result.stderr)
                self.call("prepare-handoff", "main-a", "--writers-stopped", ok=False)
                self.assertEqual(self.state_path.read_bytes(), before)


class ContinuationRequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="continuation-request-test-")
        self.addCleanup(self.temp.cleanup)
        self.prompt = Path(self.temp.name) / "接续说明 with spaces.txt"
        self.prompt.write_text("Continue the authorized task.\nPreserve the handoff ID.\n", encoding="utf-8")
        self.script = SCRIPT.with_name("create_thread_request.py")

    def request(self, *extra):
        return subprocess.run([sys.executable, str(self.script), "--project-id", "project-a",
                               "--prompt-file", str(self.prompt), *extra],
                              text=True, capture_output=True)

    def test_creation_payload_has_explicit_coordinator_model_and_effort(self):
        result = self.request("--model", "gpt-6.1-sol", "--thinking", "xhigh",
                              "--title", "接续任务")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload, {
            "model": "gpt-6.1-sol", "thinking": "xhigh", "title": "接续任务",
            "target": {"type": "project", "projectId": "project-a", "environment": {"type": "local"}},
            "prompt": self.prompt.read_text(encoding="utf-8"),
        })

    def test_user_selected_coordinator_is_preserved_without_default_fallback(self):
        result = self.request("--model", "gpt-6-astra", "--thinking", "xhigh")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual((payload["model"], payload["thinking"]), ("gpt-6-astra", "xhigh"))
        self.assertNotIn("title", payload)

    def test_omitted_model_or_effort_cannot_produce_a_request(self):
        for extra in ((), ("--model", "gpt-6.1-sol"), ("--thinking", "xhigh")):
            with self.subTest(extra=extra):
                result = self.request(*extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_blank_or_default_model_is_rejected(self):
        for model in ("", " ", "default", "client-default", "gpt-6.1-sol\nignored"):
            with self.subTest(model=model):
                result = self.request("--model", model, "--thinking", "xhigh")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_unsupported_effort_cannot_produce_a_request(self):
        result = self.request("--model", "gpt-6.1-sol", "--thinking", "default")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_missing_or_empty_prompt_cannot_produce_a_request(self):
        self.prompt.write_text(" \n")
        result = self.request("--model", "gpt-6.1-sol", "--thinking", "xhigh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.prompt.unlink()
        result = self.request("--model", "gpt-6.1-sol", "--thinking", "xhigh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()

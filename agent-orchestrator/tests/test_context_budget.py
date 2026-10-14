"""Native accounting and freshness boundaries, without live application changes."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from budget_fixture import write_native_log

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from context_budget import native_budget, transcript_context


class ContextBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="native-budget-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / "sessions").mkdir()
        self.log = self.home / "sessions" / "rollout.jsonl"
        self.records = [
            {"type": "session_meta", "payload": {"id": "owner"}},
            {"type": "turn_context", "timestamp": "2026-10-14T02:13:20Z",
             "payload": {"turn_id": "test-turn", "model": "gpt-6.1-sol"}},
            {"type": "event_msg", "timestamp": "2026-10-14T02:13:20.400Z", "payload": {
                "type": "token_count", "info": {
                    "last_token_usage": {"total_tokens": 419_131},
                    "total_token_usage": {"total_tokens": 42_688_590},
                    "model_context_window": 828_400}}},
        ]
        self.write_records()
        self.db = write_native_log(self.home, "owner", 780_878, limit=780_000)

    def write_records(self):
        self.log.write_text("".join(json.dumps(r) + "\n" for r in self.records))

    def sample(self, model="gpt-6.1-sol"):
        return native_budget(self.log, "owner", transcript_context(self.log, "owner"), model)

    def test_incident_native_780k_differs_from_api_419k_and_cumulative_42m(self):
        sample = self.sample()
        self.assertEqual((sample["tokens"], sample["api_tokens"], sample["limit"]),
                         (780_878, 419_131, 780_000))
        self.assertEqual(sample["window"], 828_400)

    def test_wrong_owner_model_or_turn_is_unverified(self):
        self.assertIsNone(transcript_context(self.log, "child"))
        self.assertIsNone(self.sample("gpt-6-astra"))
        for changes in ({"sid": "child"}, {"turn": "previous-turn"}, {"model": "gpt-6-astra"}):
            values = dict(sid="owner", tokens=780_878, limit=780_000)
            values.update(changes)
            write_native_log(self.home, **values)
            self.assertIsNone(self.sample())

    def test_precompaction_sample_is_not_reused_after_compaction(self):
        self.records.append({"type": "compacted", "timestamp": "2026-10-14T02:13:20.600Z",
                             "payload": {}})
        self.write_records()
        self.assertIsNone(self.sample())
        write_native_log(self.home, "owner", 30_000, limit=780_000, nanos=700_000_000)
        self.assertEqual(self.sample()["tokens"], 30_000)

    def test_sample_stale_relative_to_api_usage_is_unverified(self):
        self.records[-1]["timestamp"] = "2026-10-14T02:13:23Z"
        self.write_records()
        self.assertIsNone(self.sample())

    def test_unsupported_scope_or_missing_runtime_window_is_unverified(self):
        write_native_log(self.home, "owner", 419_131, scope="BodyAfterPrefix")
        self.assertIsNone(self.sample())
        for field in ("full_context_window_limit", "auto_compact_scope_limit"):
            write_native_log(self.home, "owner", 419_131)
            with closing(sqlite3.connect(self.db)) as conn, conn:
                conn.execute("UPDATE logs SET feedback_log_body=replace(feedback_log_body, ?, ?)",
                             (field + "=Some(828400)", field + "=None"))
            self.assertIsNone(self.sample())

    def test_missing_or_changed_schema_does_not_create_a_database(self):
        self.db.unlink()
        self.assertIsNone(self.sample())
        self.assertFalse(self.db.exists())
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("CREATE TABLE changed_schema (id INTEGER)")
        self.assertIsNone(self.sample())

    def test_invalid_native_fields_and_unzoned_epoch_are_unverified(self):
        for body in ("post sampling token usage total_usage_tokens=-1", "secret raw malformed log"):
            with closing(sqlite3.connect(self.db)) as conn, conn:
                conn.execute("UPDATE logs SET feedback_log_body=?", (body,))
            self.assertIsNone(self.sample())
        self.records[1]["timestamp"] = "2026-10-14T02:13:20"
        self.write_records()
        self.assertIsNone(self.sample())

    def test_identity_only_recovery_does_not_parse_damaged_body(self):
        with self.log.open("a") as stream:
            stream.write("damaged\n")
        self.assertIsNotNone(transcript_context(self.log, "owner", read_usage=False))
        with self.assertRaises(ValueError):
            transcript_context(self.log, "owner")


if __name__ == "__main__":
    unittest.main()

"""Minimal native telemetry fixture, with the same fields as Codex's log database."""

from contextlib import closing
import sqlite3


def write_native_log(home, sid, tokens, window=828_400, limit=None, model="gpt-6.1-sol",
                     turn="test-turn", seconds=1_791_944_000, nanos=500_000_000, scope="Total"):
    path = home / "logs_2.sqlite"
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, ts INTEGER, "
                     "ts_nanos INTEGER, thread_id TEXT, target TEXT, feedback_log_body TEXT)")
        conn.execute("DELETE FROM logs")
        fields = (f"turn{{model={model}}}: post sampling token usage turn_id={turn} "
                  f"total_usage_tokens={tokens} auto_compact_scope_tokens={tokens} "
                  f"auto_compact_scope_limit=Some({window if limit is None else limit}) "
                  f"auto_compact_limit_scope={scope} full_context_window_limit=Some({window})")
        conn.execute("INSERT INTO logs VALUES (1, ?, ?, ?, ?, ?)",
                     (seconds, nanos, sid, "codex_core::session::turn", fields))
    return path

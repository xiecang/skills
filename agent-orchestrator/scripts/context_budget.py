"""Read native compaction accounting without confusing it with API request usage."""

from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3


def transcript_context(path, sid, read_usage=True):
    if path is None:
        return None
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError("会话日志路径必须是非空路径。")
    context = {"api_tokens": 0, "epoch": None, "usage_at": None,
               "turn_id": None, "model": None}
    with Path(path).open(encoding="utf-8") as stream:
        first = json.loads(stream.readline())
        if (not isinstance(first, dict) or first.get("type") != "session_meta"
                or not isinstance(first.get("payload"), dict)
                or first["payload"].get("id") != sid):
            return None
        if not read_usage:
            return context
        # shortcut: rollout and native log schemas are local interfaces; recheck on client upgrades.
        for line in stream:
            if not line.endswith("\n"):
                break
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("会话日志记录必须是 JSON 对象。")
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            if record.get("type") in {"turn_context", "compacted"}:
                context["epoch"] = record.get("timestamp")
                if record["type"] == "turn_context":
                    context.update(turn_id=payload.get("turn_id"), model=payload.get("model"))
            if record.get("type") != "event_msg" or payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            last = info.get("last_token_usage") if isinstance(info, dict) else None
            if not isinstance(last, dict):
                continue
            tokens = last.get("total_tokens")
            if type(tokens) is not int or tokens < 0:
                raise ValueError("会话日志 token 计数无效。")
            context.update(api_tokens=tokens, usage_at=record.get("timestamp"))
    return context


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except ValueError:
        return None


def native_budget(path, sid, context, model):
    """Require a matching turn/model and a sample newer than the current context epoch."""
    epoch = timestamp(context["epoch"])
    if epoch is None or not context["turn_id"] or context["model"] != model:
        return None
    home = next((p.parent for p in Path(path).resolve().parents if p.name == "sessions"), None)
    if home is None:
        return None
    database = home / "logs_2.sqlite"
    if not database.is_file():
        return None
    try:
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=0.2)) as conn:
            row = conn.execute(
                "SELECT id, ts, ts_nanos, feedback_log_body FROM logs WHERE thread_id=? "
                "AND target='codex_core::session::turn' AND ts>=? "
                "AND feedback_log_body LIKE '%post sampling token usage%' "
                "ORDER BY ts DESC, ts_nanos DESC, id DESC LIMIT 1", (sid, int(epoch))).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    row_id, seconds, nanos, body = row
    if (type(seconds) is not int or type(nanos) is not int or not 0 <= nanos < 1_000_000_000):
        return None
    sampled_at = seconds + nanos / 1_000_000_000
    usage_at = timestamp(context["usage_at"])
    if sampled_at < epoch or (usage_at is not None and sampled_at + 1 < usage_at):
        return None
    if not isinstance(body, str) or "post sampling token usage " not in body:
        return None
    prefix, fields = body.rsplit("post sampling token usage ", 1)
    models = re.findall(r'\bmodel="?([A-Za-z0-9._:-]+)', prefix)
    values = dict(re.findall(r"\b([a-z_]+)=([^ ]+)", fields))
    if (not models or models[-1] != model or values.get("turn_id") != context["turn_id"]
            or values.get("auto_compact_limit_scope") != "Total"):
        return None
    try:
        tokens = int(values["total_usage_tokens"])
        scope_tokens = int(values["auto_compact_scope_tokens"])
        window = int(re.fullmatch(r"Some\((\d+)\)", values["full_context_window_limit"])[1])
        limit = int(re.fullmatch(r"Some\((\d+)\)", values["auto_compact_scope_limit"])[1])
    except (KeyError, ValueError, TypeError):
        return None
    if tokens < 0 or scope_tokens != tokens or window <= 0 or limit <= 0:
        return None
    return {"tokens": tokens, "window": window, "limit": limit, "model": model,
            "api_tokens": context["api_tokens"], "source": str(database), "row_id": row_id}

#!/usr/bin/env python3
"""agent-orchestrator: resumable early handoff for macOS/Linux."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import uuid

from context_budget import native_budget, transcript_context


STATE = "agent-orchestrator.json"
LOCK = ".agent-orchestrator.lock"
SID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
HANDOFF_COST = 35_000
REQUEST_GROWTH = 15_000
CREATION_STATES = {"not_started", "creating", "created", "failed", "unknown"}


def compaction_settings(limit, model):
    if limit is None and model is None:
        return None
    if (type(limit) is not int or limit <= 0 or not isinstance(model, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", model)):
        raise ValueError("同时提供已核实的 total 压缩阈值 --compact-limit（正整数）和 --compact-model。")
    return {"limit": limit, "model": model}


def handoff_budget(window, compact_limit=None):
    budget = min(window, compact_limit) if compact_limit is not None else window
    # Round the percentage reserve up so integer arithmetic never shrinks the margin.
    reserve = max((budget + 4) // 5, 2 * (HANDOFF_COST + REQUEST_GROWTH))
    return budget, reserve


def handoff_id(value):
    if not isinstance(value, str):
        raise ValueError("需要状态中记录的交接 ID。")
    try:
        valid = str(uuid.UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("交接 ID 格式无效。")
    return value


def session_id(value):
    if not isinstance(value, str) or not SID.fullmatch(value):
        raise ValueError("需要已核实的会话 ID；在主 agent 内运行，或显式传入 --session。")
    return value


def project_root(value):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError("需要有效的项目目录路径。")
    root = Path(value).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("项目根目录不是目录。")
    if (root / ".codegraph").is_symlink():
        raise ValueError("不通过 .codegraph 符号链接读写会话状态。")
    return root


def read_state(root):
    path = root / ".codegraph" / STATE
    if path.is_symlink():
        raise ValueError("会话状态文件不能是符号链接。")
    if not path.exists():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(state, dict) or type(state.get("version")) is not int
            or state["version"] not in {1, 2}):
        raise ValueError("会话状态格式无效；保留原文件，先核对实际任务。")
    session_id(state.get("session_id"))
    if (state.get("project_root") != str(root)
            or not isinstance(state.get("phase"), str)
            or state["phase"] not in {"active", "ready", "inactive"}
            or type(state.get("auto_continue")) is not bool
            or type(state.get("handoff_requested", False)) is not bool
            or type(state.get("handoff_budget_blocked", False)) is not bool
            or type(state.get("startup_budget_checked", True)) is not bool):
        raise ValueError("会话状态与项目或协议不匹配。")
    if "resumed_from" in state:
        session_id(state["resumed_from"])
    if "accepted_handoff_id" in state:
        handoff_id(state["accepted_handoff_id"])
    if state["version"] == 2 and "compaction_budget" in state:
        settings = state["compaction_budget"]
        if (not isinstance(settings, dict)
                or compaction_settings(settings.get("limit"), settings.get("model")) is None):
            raise ValueError("会话的压缩预算记录无效。")
    if "budget_evidence" in state:
        evidence = state["budget_evidence"]
        if not isinstance(evidence, dict) or type(evidence.get("verified")) is not bool:
            raise ValueError("会话的原生预算证据无效。")
    if state["version"] == 2 and state["phase"] == "ready":
        handoff_id(state.get("handoff_id"))
        creation = state.get("continuation")
        if (not isinstance(creation, dict) or not isinstance(creation.get("status"), str)
                or creation["status"] not in CREATION_STATES):
            raise ValueError("接续创建记录无效。")
        if creation["status"] == "created":
            if session_id(creation.get("thread_id")) == state["session_id"]:
                raise ValueError("接续聊天不能是旧主会话。")
        elif "thread_id" in creation:
            raise ValueError("未确认创建时不能登记接续聊天 ID。")
    return state


def upgrade_state(state):
    """Called only inside an owner-authorized mutation, never by status or config."""
    legacy = state["version"] == 1
    state = dict(state, version=2)
    if legacy:
        state.pop("compaction_budget", None)
    if legacy and state["phase"] == "ready":
        state.update(handoff_id=str(uuid.uuid4()), continuation={"status": "unknown"})
    return state


@contextmanager
def state_lock(root):
    directory = root / ".codegraph"
    directory.mkdir(exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
    fd = os.open(directory / LOCK, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("会话状态正在更新；重新读取状态后再试。") from error
        yield
    finally:
        os.close(fd)


def write_state(root, state):
    directory = root / ".codegraph"
    fd, name = tempfile.mkstemp(prefix=".orchestrator-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, directory / STATE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def handoff_digest(root):
    path = root / ".codegraph" / "HANDOFF.md"
    if path.is_symlink():
        raise ValueError("HANDOFF.md 不能是符号链接。")
    content = path.read_bytes()
    if not content.strip():
        raise ValueError("先完成非空的 HANDOFF.md，再释放主会话。")
    return hashlib.sha256(content).hexdigest()


def activate_state(root, state, sid, auto_continue, resume_from, expected_handoff):
    if resume_from:
        session_id(resume_from)
        handoff_id(expected_handoff)
        if (state and state["phase"] == "active" and state["session_id"] == sid
                and state.get("resumed_from") == resume_from
                and state.get("accepted_handoff_id") == expected_handoff):
            state = dict(state)
            if auto_continue is not None:
                state["auto_continue"] = auto_continue
            return state
        if (not state or state["phase"] != "ready" or state["version"] != 2
                or state["session_id"] != resume_from or sid == resume_from
                or state.get("handoff_id") != expected_handoff):
            raise ValueError("旧主会话尚未释放、未升级或交接 ID 不匹配；不得接管。")
        if state.get("handoff_sha256") != handoff_digest(root):
            raise ValueError("释放后 HANDOFF.md 已改变；先核对交接，不自动接管。")
        creation = state["continuation"]
        if creation["status"] == "created" and creation["thread_id"] != sid:
            raise ValueError("已登记另一个接续聊天；不得接管。")
        if auto_continue is None:
            auto_continue = state["auto_continue"]
    elif state and state["phase"] != "inactive":
        if state["phase"] == "active" and state["session_id"] == sid:
            state = upgrade_state(state)
            if auto_continue is not None:
                state["auto_continue"] = auto_continue
            return state
        raise ValueError("已有主会话或待接续任务；不得覆盖。先核对状态。")
    result = {"version": 2, "project_root": str(root), "session_id": sid,
              "phase": "active", "auto_continue": True if auto_continue is None else auto_continue,
              "startup_budget_checked": False}
    if resume_from:
        result.update(resumed_from=resume_from, accepted_handoff_id=expected_handoff,
                      startup_budget_checked=False)
    return result


def continuation_state(root, state, sid, action, expected_handoff, result, thread_id):
    handoff_id(expected_handoff)
    if action == "record-continuation":
        if result not in {"created", "failed", "unknown"}:
            raise ValueError("记录创建结果时需要 --result created、failed 或 unknown。")
        if result == "created":
            if session_id(thread_id) == sid:
                raise ValueError("接续聊天不能是旧主会话。")
        elif thread_id is not None:
            raise ValueError("只有 created 结果可以携带 --thread-id。")
        if (state and state.get("resumed_from") == sid
                and state.get("accepted_handoff_id") == expected_handoff):
            if result == "created" and thread_id != state["session_id"]:
                raise ValueError("回执与已接管的新主会话不符；保留当前状态。")
            return state, False
    if (not state or state["phase"] != "ready" or state["session_id"] != sid
            or state["version"] != 2 or state.get("handoff_id") != expected_handoff):
        raise ValueError("需要旧主会话持有的 v2 ready 状态及匹配的交接 ID。")
    if state.get("handoff_sha256") != handoff_digest(root):
        raise ValueError("释放后 HANDOFF.md 已改变；先核对交接，不创建或登记接续。")
    creation = state["continuation"]
    if action == "begin-continuation":
        if not state["auto_continue"]:
            raise ValueError("当前为手动接续；不得自动创建聊天。")
        if (state.get("handoff_budget_blocked", False) or state.get("startup_budget_checked") is False
                or state.get("budget_evidence", {}).get("verified") is False):
            raise ValueError("接续预算不足或首次预算尚未核实；保留现场，不自动创建聊天。")
        allowed = creation["status"] == "not_started"
        if allowed:
            state = dict(state, continuation={"status": "creating"})
        return state, allowed
    if creation["status"] == "not_started":
        raise ValueError("尚未登记创建尝试；先运行 begin-continuation。")
    if creation["status"] == "created":
        if result == "created" and thread_id != creation["thread_id"]:
            raise ValueError("创建回执中的聊天 ID 冲突；保留原记录。")
        return state, False
    receipt = {"status": result}
    if result == "created":
        receipt["thread_id"] = thread_id
    return dict(state, continuation=receipt), False


def transition(root, sid, action, auto_continue=None, resume_from=None, writers_stopped=False,
               expected_handoff=None, result=None, thread_id=None, compact_limit=None, compact_model=None):
    settings = compaction_settings(compact_limit, compact_model)
    if settings is not None and action != "activate":
        raise ValueError("压缩预算只能由当前持有者在 activate 时登记。")
    with state_lock(root):
        state = read_state(root)
        before = state
        if action in {"begin-continuation", "record-continuation"}:
            state, allowed = continuation_state(root, state, sid, action, expected_handoff,
                                               result, thread_id)
        elif action == "activate":
            if expected_handoff is not None and not resume_from:
                raise ValueError("--handoff-id 必须与 --resume-from 一起使用。")
            state = activate_state(root, state, sid, auto_continue, resume_from, expected_handoff)
            if settings is not None:
                state = dict(state, compaction_budget=settings)
        else:
            if not state or state["session_id"] != sid:
                raise ValueError("只有登记的主会话可以释放或撤销自己的标记。")
            if action == "prepare-handoff":
                if not writers_stopped or state["phase"] not in {"active", "ready"}:
                    raise ValueError("先确认活动写入停止，再用 --writers-stopped 释放。")
                digest = handoff_digest(root)
                if state["phase"] == "ready" and state.get("handoff_sha256") != digest:
                    raise ValueError("已释放的交接文档发生变化；不得覆盖待接续状态。")
                state = upgrade_state(state)
                if state["phase"] == "active":
                    state.update(handoff_id=str(uuid.uuid4()), continuation={"status": "not_started"})
                state.update(phase="ready", handoff_sha256=digest)
            elif action == "deactivate":
                if state["phase"] == "ready":
                    raise ValueError("已释放的交接不能由旧会话撤销；先核对并完成接管。")
                state = upgrade_state(state)
                state["phase"] = "inactive"
            else:
                raise ValueError("未知状态操作。")
        if state != before:
            write_state(root, state)
        if action == "begin-continuation":
            return {"create_allowed": allowed, "state": state}
        return state


def registered_session(event):
    sid = session_id(event.get("session_id"))
    cwd = project_root(event["cwd"])
    for root in (cwd, *cwd.parents):
        if (root / ".codegraph" / STATE).exists():
            root = project_root(root)
            state = read_state(root)
            if not state:
                return None
            previous = state.get("resumed_from") == sid and state.get("accepted_handoff_id")
            if not previous and (state["session_id"] != sid or state["phase"] == "inactive"):
                return None
            return root, state
    return None


def request_handoff(root, sid):
    with state_lock(root):
        state = read_state(root)
        if (not state or state["session_id"] != sid or state["phase"] != "active"
                or state.get("handoff_requested", False)
                or state.get("startup_budget_checked") is False
                or state.get("handoff_budget_blocked", False)):
            return None
        state = upgrade_state(state)
        state["handoff_requested"] = True
        write_state(root, state)
        return state


def set_budget_blocked(root, sid, blocked, tokens=None, threshold=None, expected_compaction=None,
                       evidence=None):
    with state_lock(root):
        state = read_state(root)
        if (not state or state["session_id"] != sid or state["phase"] != "active"
                or state.get("handoff_requested", False)):
            return None
        # A concurrent settings update invalidates the threshold calculated by this hook.
        if state.get("compaction_budget") != expected_compaction:
            return None
        updated = dict(state)
        if evidence is not None:
            updated["budget_evidence"] = evidence
        startup = state.get("startup_budget_checked") is False
        if startup or state.get("handoff_budget_blocked", False):
            if tokens is not None and tokens > 0 and threshold is not None:
                if state.get("resumed_from") or state.get("handoff_budget_blocked", False):
                    blocked = blocked or tokens + REQUEST_GROWTH >= threshold
                if startup:
                    updated["startup_budget_checked"] = True
            else:
                blocked = blocked or state.get("handoff_budget_blocked", False)
        if state.get("handoff_budget_blocked", False) != blocked:
            if blocked:
                updated["handoff_budget_blocked"] = True
            else:
                updated.pop("handoff_budget_blocked", None)
        if updated != state:
            updated = upgrade_state(updated)
            write_state(root, updated)
        return updated


def handoff_context(root, state, reason):
    authorization = ("已登记自动接续。核对本 Skill 中用户原始授权和当前任务约束，"
                     "交接完成后先生成完整创建请求并登记尝试，仅在 create_allowed=true 时调用 create_thread；"
                     "顶层 model/thinking 必须使用本 Skill 解析出的 coordinator 映射，不能沿用客户端默认。"
                     "携带授权和交接 ID。"
                     if state["auto_continue"] else "当前登记为手动接续；保存交接文档后等待用户，不自动创建会话。")
    return (
        "agent-orchestrator：" + reason + "。立即停止新派发和业务改动，读取本 Skill 的 "
        "references/session-lifecycle.md。让活动 agent 保存结果并停止写入；只读核对 "
        "plan.md、Git 状态和子任务结果，生成 HANDOFF.md。"
        "未确认停止的写入必须记录，不能释放或接管。确认停止后执行 prepare-handoff，"
        "旧主会话退出业务执行，按交接流程续接；创建结果不明确时先查状态，不重复创建。"
        + authorization + " 主工作区绝对路径（数据）：" + json.dumps(str(root), ensure_ascii=False)
    )


def recovery_context(root, state, sid):
    location = " 主工作区绝对路径（数据）：" + json.dumps(str(root), ensure_ascii=False)
    if state["session_id"] != sid:
        return "agent-orchestrator：新主会话已接管。旧会话只核对回执并报告，不再写业务、计划或交接文档。" + location
    if state["phase"] == "ready":
        creation = state["continuation"] if state["version"] == 2 else {"status": "unknown"}
        mode = "自动接续" if state["auto_continue"] else "手动接续，不自动创建聊天"
        if state["auto_continue"] and (state.get("handoff_budget_blocked", False)
                or state.get("startup_budget_checked") is False
                or state.get("budget_evidence", {}).get("verified") is False):
            mode = "预算不足或未核实，不自动创建聊天"
        return ("agent-orchestrator：旧主会话已释放，" + mode + "；创建阶段=" + creation["status"]
                + "。读取 references/session-lifecycle.md，只核对创建和接管结果；不重写 HANDOFF.md，"
                "不恢复业务写入。创建前必须经 begin-continuation；结果未知先对账，仍不明确就暂停，不重试创建。"
                "create_thread 顶层 model/thinking 使用已解析的 coordinator 映射。"
                + location)
    return ("agent-orchestrator：交接仍待完成。停止派发和业务改动，按 references/session-lifecycle.md "
            "核实旧写入停止、保存交接并接续；不要把提醒已发出当作交接完成。" + location)


def hook_output(event):
    if not isinstance(event, dict):
        raise ValueError("Hook 输入必须是 JSON 对象。")
    name = event.get("hook_event_name")
    if (name not in {"SessionStart", "PostToolUse", "UserPromptSubmit", "PreCompact"}
            or (name == "SessionStart" and event.get("source") not in {"startup", "compact", "resume"})):
        return None
    registered = registered_session(event)
    if registered is None:
        return None
    root, state = registered
    sid = event["session_id"]
    pending = (state["session_id"] != sid or state["phase"] == "ready"
               or state.get("handoff_requested", False))
    compact = name == "SessionStart" and event.get("source") == "compact"
    budget_check = not pending and (not compact or state.get("startup_budget_checked") is False
                                   or state.get("handoff_budget_blocked", False))
    context = transcript_context(event.get("transcript_path"), sid,
                                 read_usage=budget_check or name == "PreCompact")
    if context is None:
        return None
    model = event.get("model")
    if budget_check and event.get("turn_id") not in (None, context["turn_id"]):
        model = None
    if name == "PreCompact":
        sample = native_budget(event.get("transcript_path"), sid, context, model)
        detail = (f"原生计数 {sample['tokens']}，实际压缩线 {sample['limit']}，"
                  f"API 单次用量 {sample['api_tokens']}" if sample else "原生压缩预算未核实")
        return {"systemMessage": "agent-orchestrator：压缩前观测（"
                + str(event.get("trigger", "unknown")) + "）：" + detail
                + "；本 hook 不阻断压缩，压缩后按恢复交接处理。"}
    if pending:
        return {"hookSpecificOutput": {"hookEventName": name,
                                       "additionalContext": recovery_context(root, state, sid)}}
    reason = "主会话已意外压缩，进入恢复交接"
    if budget_check:
        sample = native_budget(event.get("transcript_path"), sid, context, model)
        if sample is None:
            set_budget_blocked(root, sid, False, expected_compaction=state.get("compaction_budget"),
                               evidence={"verified": False})
            return {"hookSpecificOutput": {"hookEventName": name, "additionalContext":
                    "agent-orchestrator：原生计数或运行时窗口未知，实际压缩预算未核实。"
                    "先停止新派发，执行一次小输出预算检查；不要用 API 单次或累计用量代替。"
                    "日志缺失、过期或口径不兼容时报告限制，不推算固定交接线。"}}
        tokens, window = sample["tokens"], sample["window"]
        verified = state.get("compaction_budget") if state["version"] == 2 else None
        compact_limit = sample["limit"]
        if verified and verified["model"] == sample["model"]:
            compact_limit = min(compact_limit, verified["limit"])
        budget, reserve = handoff_budget(window, compact_limit)
        threshold = budget - reserve
        state = set_budget_blocked(root, sid, reserve >= budget, tokens=tokens, threshold=threshold,
                                   expected_compaction=state.get("compaction_budget"),
                                   evidence=dict(sample, verified=True, threshold=threshold))
        if state is None:
            return None
        if state.get("handoff_budget_blocked", False):
            return {"hookSpecificOutput": {"hookEventName": name, "additionalContext":
                    f"agent-orchestrator：交接预算不足或接续启动余量不足（预算 {budget}，"
                    f"预留 {reserve}，计数 {tokens}，交接线 {threshold}）。"
                    "停止新派发，保存现场并报告容量不足；先缩短交接或核对模型窗口，不自动反复创建聊天。"}}
        if state.get("startup_budget_checked") is False:
            return {"hookSpecificOutput": {"hookEventName": name, "additionalContext":
                    "agent-orchestrator：接续首次预算尚未核实。等待有效窗口和正数计数，再判断是否交接；"
                    "不自动创建下一聊天。"}}
        if not compact and tokens < threshold:
            return None
        if not compact:
            reason = (f"原生上下文计数 {tokens}，达到提前交接线 {threshold}"
                      f"（预算 {budget}，预留 {reserve}；API 单次用量 {sample['api_tokens']}）")
    state = request_handoff(root, sid)
    if state is None:
        return None
    return {"hookSpecificOutput": {"hookEventName": name,
                                   "additionalContext": handoff_context(root, state, reason)}}


def configuration():
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), "hook"])
    groups = []
    for name, matcher, label in [
        ("SessionStart", "^(startup|compact|resume)$", "agent-orchestrator：恢复与交接接续"),
        ("PostToolUse", "", "agent-orchestrator：提前自动交接"),
        ("UserPromptSubmit", "", "agent-orchestrator：新输入预算检查"),
        ("PreCompact", "^(auto|manual)$", "agent-orchestrator：压缩前观测"),
    ]:
        groups.append(f"[[hooks.{name}]]\nmatcher = {json.dumps(matcher)}\n\n"
                      f"[[hooks.{name}.hooks]]\ntype = \"command\"\ncommand = "
                      + json.dumps(command, ensure_ascii=False) + "\ntimeout = 5\n"
                      + "statusMessage = " + json.dumps(label, ensure_ascii=False) + "\n")
    return "\n".join(groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("config", help="只打印 hook 配置，不修改全局文件")
    sub.add_parser("hook", help="读取一次 Codex hook 的 stdin")
    for action in ("activate", "prepare-handoff", "deactivate", "status", "check-budget",
                   "begin-continuation", "record-continuation"):
        command = sub.add_parser(action)
        command.add_argument("--root", required=True, help="主协调者工作区的项目根目录")
        if action != "status":
            command.add_argument("--session", default=os.environ.get("CODEX_THREAD_ID"))
        if action == "check-budget":
            command.add_argument("--transcript-path", required=True)
            command.add_argument("--model", required=True)
        if action == "activate":
            mode = command.add_mutually_exclusive_group()
            mode.add_argument("--auto-continue", action="store_true", default=None,
                              help="按本机用户已登记偏好自动接续（新任务默认）；仍需核对任务授权")
            mode.add_argument("--manual-continue", action="store_false", dest="auto_continue",
                              default=None,
                              help="本任务只保存交接，不自动创建聊天")
            command.add_argument("--resume-from", help="HANDOFF 中记录的旧主会话 ID")
            command.add_argument("--compact-limit", type=int,
                                 help="仅登记已核实对此会话生效的 total 压缩阈值；不修改 Codex 配置")
            command.add_argument("--compact-model", help="上述已核实阈值对应的实际模型 ID")
        if action in {"activate", "begin-continuation", "record-continuation"}:
            command.add_argument("--handoff-id", required=action != "activate",
                                 help="prepare-handoff 返回的唯一交接 ID；接管时必须携带")
        if action == "record-continuation":
            command.add_argument("--result", required=True, choices=("created", "failed", "unknown"))
            command.add_argument("--thread-id", help="客户端实际返回或核实的接续聊天 ID")
        if action == "prepare-handoff":
            command.add_argument("--writers-stopped", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "config":
            print(configuration(), end="")
            return 0
        if args.action == "hook":
            output = hook_output(json.load(sys.stdin))
            if output is not None:
                print(json.dumps(output, ensure_ascii=False))
            return 0
        root = project_root(args.root)
        if args.action == "check-budget":
            result = hook_output({"session_id": session_id(args.session), "cwd": str(root),
                                  "hook_event_name": "PostToolUse", "model": args.model,
                                  "transcript_path": args.transcript_path})
        elif args.action == "status":
            result = read_state(root) or {"phase": "unregistered"}
        else:
            result = transition(root, session_id(args.session), args.action,
                                getattr(args, "auto_continue", None),
                                getattr(args, "resume_from", None),
                                getattr(args, "writers_stopped", False),
                                getattr(args, "handoff_id", None),
                                getattr(args, "result", None),
                                getattr(args, "thread_id", None),
                                getattr(args, "compact_limit", None),
                                getattr(args, "compact_model", None))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"agent-orchestrator: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

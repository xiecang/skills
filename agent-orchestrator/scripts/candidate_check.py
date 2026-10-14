#!/usr/bin/env python3
"""Bind an authorized local check to its actual workdir and frozen Git inputs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def absolute(value, follow_links=True):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Use absolute workspace, workdir and evidence paths.")
    return path.resolve() if follow_links else path


def workspace(root, head, workdir):
    if Path.cwd().resolve() != workdir:
        raise ValueError("Actual cwd does not match the declared workdir; command not executed.")
    if workdir != root and root not in workdir.parents:
        raise ValueError("Workdir is outside the candidate workspace.")
    if Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).strip()).resolve() != root:
        raise ValueError("Workspace must be the exact Git worktree root.")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", head):
        raise ValueError("Expected HEAD must be a verified full commit ID.")
    if git(root, "rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("Candidate HEAD changed.")


def file_identity(path, missing=False):
    if not path.exists() and not path.is_symlink():
        if missing:
            return None
        raise ValueError("Declared input is missing: " + str(path))
    if not path.is_file():
        raise ValueError("Directory, submodule or broken-link input needs project-native evidence: " + str(path))
    result = {"sha256": file_sha(path), "mode": stat.S_IMODE(path.stat().st_mode)}
    if path.is_symlink():
        result["link"] = os.readlink(path)
    return result


def snapshot(root, extra_inputs):
    names = set(os.fsdecode(git(root, "ls-files", "-z", "--cached", "--others",
                               "--exclude-standard")).split("\0")) - {""}
    files = {name: file_identity(root / name, missing=True) for name in sorted(names)}
    extras = {name: file_identity(absolute(name, follow_links=False)) for name in extra_inputs}
    return {"files": files, "extra_inputs": extras}


def artifact(value, root, inputs):
    path = absolute(value)
    for flag in ("--absolute-git-dir", "--git-common-dir"):
        directory = Path(os.fsdecode(git(root, "rev-parse", flag)).strip())
        directory = (root / directory).resolve() if not directory.is_absolute() else directory.resolve()
        if path == directory or directory in path.parents:
            raise ValueError("Evidence cannot be written into Git metadata.")
    if any(path == absolute(name) for name in inputs["extra_inputs"]):
        raise ValueError("Evidence path collides with a declared input.")
    if root in path.parents:
        relative = str(path.relative_to(root))
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "--quiet", "--", relative],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE).returncode == 0
        if relative in inputs["files"] or not ignored:
            raise ValueError("Evidence inside the worktree must be Git-ignored and outside candidate inputs.")
    return path


def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    return os.fdopen(fd, "wb")


def write_json(path, value):
    data = (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()
    with exclusive(path) as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(data)


def capture(args):
    root = absolute(args.workspace)
    workspace(root, args.head, root)
    extras = sorted({str(absolute(name, follow_links=False)) for name in args.input})
    inputs = snapshot(root, extras)
    output = artifact(args.output, root, inputs)
    if inputs != snapshot(root, extras):
        raise ValueError("Inputs changed during capture; stop writers and retry.")
    workspace(root, args.head, root)
    manifest = dict(version=1, workspace=str(root), head=args.head, **inputs)
    digest = write_json(output, manifest)
    return {"manifest": str(output), "manifest_sha256": digest, "workspace": str(root), "head": args.head}


def candidate(args):
    path = absolute(args.manifest)
    data = path.read_bytes()
    if sha(data) != args.manifest_sha256:
        raise ValueError("Manifest digest differs from the frozen candidate.")
    manifest = json.loads(data)
    if (not isinstance(manifest, dict)
            or type(manifest.get("version")) is not int or manifest["version"] != 1
            or not isinstance(manifest.get("files"), dict)
            or not isinstance(manifest.get("extra_inputs"), dict)):
        raise ValueError("Invalid candidate manifest.")
    root, workdir = absolute(manifest["workspace"]), absolute(args.workdir)
    workspace(root, manifest["head"], workdir)
    if snapshot(root, manifest["extra_inputs"]) != {key: manifest[key] for key in ("files", "extra_inputs")}:
        raise ValueError("Current inputs differ from the frozen candidate.")
    return manifest, root, workdir


def group_exists(group):
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # macOS may report EPERM for a zombie group; retain unknown until reaped.
        return True


def stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return True
    except PermissionError:
        pass
    deadline = time.monotonic() + 5
    while group_exists(process.pid) and time.monotonic() < deadline:
        process.poll()
        time.sleep(0.05)
    if group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    process.wait()
    deadline = time.monotonic() + 2
    while group_exists(process.pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not group_exists(process.pid)


def execute(command, stream, workdir):
    with subprocess.Popen(command, cwd=workdir, stdout=stream, stderr=subprocess.STDOUT,
                          start_new_session=True) as process:
        try:
            code = process.wait()
            if group_exists(process.pid):
                return code, True, stop_group(process)
            return code, False, True
        except KeyboardInterrupt:
            stopped = stop_group(process)
            return process.returncode, True, stopped


def command_args(args):
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise ValueError("Supply the exact check command after --.")
    return command


def run(args):
    manifest, root, workdir = candidate(args)
    command = command_args(args)
    log = artifact(args.log, root, manifest)
    receipt = artifact(args.receipt, root, manifest)
    if log == receipt or log == absolute(args.manifest) or receipt == absolute(args.manifest):
        raise ValueError("Manifest, log and receipt paths must be different.")
    if log.exists() or receipt.exists():
        raise ValueError("Use new evidence paths; existing evidence is preserved.")
    started = time.monotonic()
    error, code, interrupted, stopped = None, None, False, False
    with exclusive(log) as stream:
        try:
            code, interrupted, stopped = execute(command, stream, workdir)
        except OSError as exc:
            error = str(exc)
    matches = True
    try:
        candidate(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        matches, error = False, str(exc)
    result = {"version": 1, "workspace": str(root), "head": manifest["head"],
              "workdir": str(workdir), "manifest_sha256": args.manifest_sha256,
              "command": command, "command_exit": code, "interrupted": interrupted,
              "process_group_stopped": stopped, "inputs_match": matches,
              "valid": code == 0 and not interrupted and stopped and matches and error is None,
              "log": str(log), "log_sha256": file_sha(log),
              "duration_seconds": round(time.monotonic() - started, 3), "error": error}
    write_json(receipt, result)
    status = (130 if interrupted else 128 - code if code is not None and code < 0
              else code if code else 1)
    return {"receipt": str(receipt), **result}, 0 if result["valid"] else status


def verify(args):
    manifest, root, workdir = candidate(args)
    receipt = json.loads(absolute(args.receipt).read_bytes())
    if not isinstance(receipt, dict):
        raise ValueError("Invalid check receipt.")
    expected = {"workspace": str(root), "head": manifest["head"], "workdir": str(workdir),
                "manifest_sha256": args.manifest_sha256, "command": command_args(args)}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Receipt does not cover the declared candidate, workdir and command.")
    if (type(receipt.get("version")) is not int or receipt["version"] != 1
            or type(receipt.get("command_exit")) is not int or receipt["command_exit"] != 0
            or receipt.get("valid") is not True or receipt.get("inputs_match") is not True
            or receipt.get("process_group_stopped") is not True
            or receipt.get("interrupted") is not False or receipt.get("error") is not None):
        raise ValueError("Check failed, was interrupted or lacks valid input evidence.")
    log = artifact(receipt["log"], root, manifest)
    if file_sha(log) != receipt.get("log_sha256"):
        raise ValueError("Check log changed or is missing.")
    return {"valid": True, "receipt": str(absolute(args.receipt)), **expected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--workspace", required=True)
    cap.add_argument("--head", required=True)
    cap.add_argument("--output", required=True)
    cap.add_argument("--input", action="append", default=[], help="Additional ignored/external input file")
    for action in ("run", "verify"):
        cmd = sub.add_parser(action)
        for name in ("manifest", "manifest-sha256", "workdir", "receipt"):
            cmd.add_argument("--" + name, required=True)
        if action == "run":
            cmd.add_argument("--log", required=True)
        cmd.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == "run":
            result, status = run(args)
        else:
            result, status = (capture(args) if args.action == "capture" else verify(args)), 0
        print(json.dumps(result, ensure_ascii=True))
        return status
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print("candidate-check: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

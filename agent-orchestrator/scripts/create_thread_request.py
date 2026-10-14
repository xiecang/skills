#!/usr/bin/env python3
"""Print a create_thread request for a resolved, runtime-verified coordinator."""

import argparse
import json
from pathlib import Path
import re
import sys


def model_id(value):
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", value)
            or value.lower() in {"default", "client-default", "auto", "inherit", "current", "coordinator"}):
        raise argparse.ArgumentTypeError("需要已核实的 coordinator 模型 ID，不能使用客户端默认或角色别名。")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--model", required=True, type=model_id)
    parser.add_argument("--thinking", required=True,
                        choices=("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"))
    parser.add_argument("--title")
    parser.add_argument("--use-verified-client-defaults", action="store_true",
                        help="仅在客户端默认模型/effort已核实匹配上述解析值、且工具要求省略覆盖时使用")
    args = parser.parse_args()
    try:
        if not args.project_id.strip() or args.project_id != args.project_id.strip():
            raise ValueError("需要 list_projects 返回的实际本地项目 ID。")
        prompt = args.prompt_file.read_text(encoding="utf-8")
        if not prompt.strip():
            raise ValueError("接续提示不能为空。")
        request = {"target": {"type": "project", "projectId": args.project_id,
                              "environment": {"type": "local"}}, "prompt": prompt}
        if args.use_verified_client_defaults:
            request["prompt"] += ("\nExpected coordinator runtime (verify before takeover/business execution): "
                                  + args.model + " / " + args.thinking + ".\n")
        else:
            request.update(model=args.model, thinking=args.thinking)
        if args.title is not None:
            request["title"] = args.title
        print(json.dumps(request, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(f"agent-orchestrator: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

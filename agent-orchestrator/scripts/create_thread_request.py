#!/usr/bin/env python3
"""Print a complete create_thread request with an explicitly resolved coordinator."""

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
    args = parser.parse_args()
    try:
        if not args.project_id.strip() or args.project_id != args.project_id.strip():
            raise ValueError("需要 list_projects 返回的实际本地项目 ID。")
        prompt = args.prompt_file.read_text(encoding="utf-8")
        if not prompt.strip():
            raise ValueError("接续提示不能为空。")
        request = {"model": args.model, "thinking": args.thinking,
                   "target": {"type": "project", "projectId": args.project_id,
                              "environment": {"type": "local"}}, "prompt": prompt}
        if args.title is not None:
            request["title"] = args.title
        print(json.dumps(request, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(f"agent-orchestrator: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

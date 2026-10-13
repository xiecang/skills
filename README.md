# skills

Source repository for personal Codex Skills. Each Skill has a separate directory containing its execution rules and supporting resources.

| Skill | Purpose | Setup and maintenance |
| --- | --- | --- |
| [agent-orchestrator](agent-orchestrator/SKILL.md) | Scoped multi-model work, independent review, and resumable handoff. | [README](agent-orchestrator/README.md) |

Validate from the repository root:

```bash
python3 agent-orchestrator/tests/test_session_hook.py
```

Install each Skill from its verified source directory using its README. The repository root is a collection, not an installable Skill. Maintaining a Skill does not start its business workflow or modify live project state.

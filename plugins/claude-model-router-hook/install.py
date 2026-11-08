#!/usr/bin/env python3
"""
Manual (non-plugin) installer for claude-model-router-hook -- cross-platform.

Python port of install.sh that also runs on Windows (no bash required).
When installed as a Claude Code plugin, hooks/hooks.json auto-registers the
four Python entrypoints and no manual step is needed. This script mirrors
that setup for a manual clone-and-install into ~/.claude.

Usage: python install.py
"""

import json
import pathlib
import platform
import shutil
import subprocess
import sys

ENTRYPOINTS = [
    # (file, hook event, matcher, timeout)
    ("session_init.py", "SessionStart", None, 5),
    ("user_prompt_submit.py", "UserPromptSubmit", None, 10),
    ("pre_tool_use.py", "PreToolUse", "Agent|Task", 10),
    ("post_tool_use.py", "PostToolUse", "Agent|Task", 5),
]


def python_command():
    """The interpreter name to put in settings.json hook commands."""
    if platform.system() == "Windows":
        # `python3` on Windows is often the Microsoft Store alias stub.
        return "python"
    return "python3"


def main():
    if sys.version_info < (3, 8):
        sys.exit("Python 3.8+ is required.")

    script_dir = pathlib.Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent

    claude_dir = pathlib.Path.home() / ".claude"
    hooks_dir = claude_dir / "hooks"
    agents_dir = claude_dir / "agents"
    schema_dir = claude_dir / "schema"

    print(f"Installing claude-model-router-hook (v2) to {claude_dir}")

    for d in (hooks_dir, agents_dir, schema_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Router package
    shutil.rmtree(hooks_dir / "router", ignore_errors=True)
    shutil.copytree(
        script_dir / "hooks" / "router",
        hooks_dir / "router",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    # Python entrypoints
    for name, _, _, _ in ENTRYPOINTS:
        shutil.copy2(script_dir / "hooks" / name, hooks_dir / name)

    # Routed agent variants, generated from the resolved config so only tiers
    # the config actually targets get an agent file. A failure aborts the
    # install (same reasoning as install.sh).
    sys.stdout.flush()
    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "generate_variants.py"),
            "--agents-dir",
            str(agents_dir),
            "--use-user-config",
        ]
    )
    if result.returncode != 0:
        sys.exit(result.returncode)

    # Config schema (v1 + v2 shapes)
    shutil.copy2(
        repo_root / "schema" / "model-router.schema.json",
        schema_dir / "model-router.schema.json",
    )

    print()
    print("Installed:")
    print(f"  hooks/router/                     -> {hooks_dir / 'router'}")
    for name, _, _, _ in ENTRYPOINTS:
        print(f"  hooks/{name:<28}-> {hooks_dir / name}")
    print(f"  agents/routed-*.md                -> {agents_dir}")
    print(f"  schema/model-router.schema.json   -> {schema_dir}")

    py = python_command()
    hooks_dir_str = hooks_dir.as_posix()
    snippet = {"hooks": {}}
    for name, event, matcher, timeout in ENTRYPOINTS:
        group = {
            "hooks": [
                {
                    "type": "command",
                    "command": f'{py} "{hooks_dir_str}/{name}"',
                    "timeout": timeout,
                }
            ]
        }
        if matcher:
            group = {"matcher": matcher, **group}
        snippet["hooks"][event] = [group]

    print()
    print("Merge the following into ~/.claude/settings.json:")
    print()
    print(json.dumps(snippet, indent=2))
    print()
    print(f"Routed subagent variants installed to {agents_dir}, one per configured class target (listed above).")
    print()
    print("Then restart Claude Code.")


if __name__ == "__main__":
    main()

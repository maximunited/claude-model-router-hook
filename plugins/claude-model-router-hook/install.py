#!/usr/bin/env python3
"""
Manual (non-plugin) installer for claude-model-router-hook -- cross-platform.

Python port of install.sh that also runs on Windows (no bash required).
When installed as a Claude Code plugin, hooks/hooks.json auto-registers the
four Python entrypoints and no manual step is needed. This script mirrors
that setup for a manual clone-and-install into ~/.claude.

Usage: python3 install.py   (Windows: py install.py)
"""

import json
import pathlib
import shutil
import subprocess
import sys

MIN_PYTHON = (3, 10)  # router/ladder.py uses PEP 604 `X | None` annotations
PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}/hooks/"


def hook_registrations(script_dir, hooks_dir):
    """Derive settings.json hook entries from hooks/hooks.json (single source of
    truth), pointed at the installed copies and at the interpreter running this
    installer -- which is known to be new enough, unlike whatever `python` or
    `python3` resolves to on PATH."""
    spec = json.loads((script_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    interpreter = pathlib.Path(sys.executable).as_posix()
    target = hooks_dir.as_posix() + "/"
    for event, groups in spec["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                cmd = hook["command"]
                if not cmd.startswith("python3 ") or PLUGIN_ROOT_TOKEN not in cmd:
                    raise SystemExit(f"Unexpected hook command in hooks.json: {cmd!r}")
                script = cmd[len("python3 "):].replace(PLUGIN_ROOT_TOKEN, target).strip().strip('"')
                hook["command"] = _shell_command(interpreter, script)
            yield event, group


def _shell_command(interpreter, script):
    """One command line that parses under PowerShell, cmd.exe and sh.

    Claude Code on Windows hands hook commands to PowerShell, where a line
    that *starts* with a quoted string is a ParserError (a string literal
    followed by another token), so quoting the interpreter path breaks every
    hook. Paths without spaces need no quotes in any of the three shells.
    A path with spaces gets the PowerShell call operator, which cmd and sh
    cannot parse, so the installer says so rather than emitting it silently.
    """
    if " " not in interpreter and " " not in script:
        return f"{interpreter} {script}"
    print(
        "Note: a path contains spaces; the printed commands use PowerShell's "
        "call operator (&). On a host that runs hooks through cmd.exe or sh, "
        "move Python or the hooks directory to a space-free path instead."
    )
    return f'& "{interpreter}" "{script}"'


def entrypoint_files(script_dir):
    spec = json.loads((script_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    names = []
    for groups in spec["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                names.append(hook["command"].split(PLUGIN_ROOT_TOKEN, 1)[1].strip('"'))
    return names


def main():
    if sys.version_info < MIN_PYTHON:
        sys.exit(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required (found {sys.version.split()[0]}).")

    script_dir = pathlib.Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent

    claude_dir = pathlib.Path.home() / ".claude"
    hooks_dir = claude_dir / "hooks"
    agents_dir = claude_dir / "agents"
    schema_dir = claude_dir / "schema"

    print(f"Installing claude-model-router-hook (v2) to {claude_dir}")

    for d in (hooks_dir, agents_dir, schema_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Routed agent variants first: the generator imports the router package
    # from this repo, so a conflict or failure aborts before any installed hook
    # code is touched (no half-upgraded state).
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

    # Router package
    router_dst = hooks_dir / "router"
    try:
        if router_dst.exists():
            shutil.rmtree(router_dst)
        shutil.copytree(
            script_dir / "hooks" / "router",
            router_dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    except OSError as exc:
        sys.exit(
            f"Could not replace {router_dst}: {exc}\n"
            "Close any running Claude Code sessions and re-run the installer."
        )

    # Python entrypoints
    entrypoints = entrypoint_files(script_dir)
    for name in entrypoints:
        shutil.copy2(script_dir / "hooks" / name, hooks_dir / name)

    # Config schema (v1 + v2 shapes)
    shutil.copy2(
        repo_root / "schema" / "model-router.schema.json",
        schema_dir / "model-router.schema.json",
    )

    print()
    print("Installed:")
    print(f"  hooks/router/                     -> {router_dst}")
    for name in entrypoints:
        print(f"  hooks/{name:<28}-> {hooks_dir / name}")
    print(f"  agents/routed-*.md                -> {agents_dir}")
    print(f"  schema/model-router.schema.json   -> {schema_dir}")

    print()
    print("Register the following in ~/.claude/settings.json.")
    print("APPEND each entry to the existing array for its event -- do not replace")
    print("the arrays, or any hooks you already have for that event are dropped.")
    for event, group in hook_registrations(script_dir, hooks_dir):
        print()
        print(f'Under "hooks" > "{event}":')
        print("  " + json.dumps(group))
    print()
    print(f"Routed subagent variants installed to {agents_dir}, one per configured class target (listed above).")
    print()
    print("Then restart Claude Code.")


if __name__ == "__main__":
    main()

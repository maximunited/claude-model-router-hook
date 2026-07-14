"""
Cross-platform installer for claude-model-router-hook.
Works on Windows, macOS, and Linux. Requires Python 3.6+.

Usage: python install.py
"""

import os
import pathlib
import platform
import shutil
import stat
import sys


def main():
    hooks_dir = pathlib.Path.home() / ".claude" / "hooks"
    script_dir = pathlib.Path(__file__).resolve().parent
    plugin_hooks = script_dir / "plugins" / "claude-model-router-hook" / "hooks"

    print(f"Installing claude-model-router-hook to {hooks_dir}")
    hooks_dir.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        "session_init.py",
        "prompt_router.py",
        "model_router.py",
        "session-init.sh",
        "model-router-hook.sh",
    ]

    for filename in files_to_copy:
        src = plugin_hooks / filename
        dst = hooks_dir / filename
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {filename}")
        else:
            print(f"  Skipped {filename} (not found)")

    if platform.system() != "Windows":
        for sh_file in ["session-init.sh", "model-router-hook.sh"]:
            path = hooks_dir / sh_file
            if path.exists():
                path.chmod(path.stat().st_mode | stat.S_IEXEC)

    hooks_dir_str = str(hooks_dir).replace("\\", "/")

    py_cmd = "python3"
    if platform.system() == "Windows":
        py_cmd = "python"

    print()
    print("Hooks installed. Add the following to ~/.claude/settings.json:")
    print()
    print('Under "hooks" > "SessionStart":')
    print(f'  {{ "type": "command", "command": "{py_cmd} \\"{hooks_dir_str}/session_init.py\\"", "timeout": 2 }}')
    print()
    print('Under "hooks" > "UserPromptSubmit":')
    print('  "UserPromptSubmit": [')
    print('    {')
    print('      "matcher": "",')
    print('      "hooks": [')
    print(f'        {{ "type": "command", "command": "{py_cmd} \\"{hooks_dir_str}/prompt_router.py\\"", "timeout": 2 }}')
    print('      ]')
    print('    }')
    print('  ]')
    print()
    print("Then restart Claude Code.")


if __name__ == "__main__":
    main()

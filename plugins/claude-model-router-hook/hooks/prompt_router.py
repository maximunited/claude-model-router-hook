"""
Prompt router hook (UserPromptSubmit) — cross-platform replacement for model-router-hook.sh.

Delegates to model_router.main() directly, capturing stdout/stderr and relaying the exit code.
Adapted from model-matchmaker (https://github.com/coyvalyss1/model-matchmaker)
"""

import io
import os
import pathlib
import sys


def main():
    hooks_dir = pathlib.Path.home() / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hook_dir = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(hook_dir))

    import model_router

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    sys.stdout = captured_stdout
    sys.stderr = captured_stderr

    exit_code = 0
    try:
        model_router.main()
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 0

    sys.stdout = old_stdout
    sys.stderr = old_stderr

    stdout_result = captured_stdout.getvalue()
    stderr_result = captured_stderr.getvalue()

    if exit_code == 2:
        print(stderr_result, end="", file=sys.stderr)
        sys.exit(2)

    if stdout_result:
        print(stdout_result, end="")

    sys.exit(0)


if __name__ == "__main__":
    main()

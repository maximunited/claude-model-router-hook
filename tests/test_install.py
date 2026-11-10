"""Tests for the manual installer (plugins/claude-model-router-hook/install.py).

Covers bug #1: Claude Code on Windows runs hook commands through PowerShell,
where a line starting with a quoted string is a ParserError, so a quoted
interpreter path broke every hook at session start. install._shell_command and
install.hook_registrations are the fix; these tests pin the printed command
shape and, on Windows with PowerShell available, actually execute the printed
commands to prove they parse and run instead of only asserting on strings.

Every test here is sandboxed to temp directories: hook_registrations is always
called with a temp hooks_dir, and the PowerShell execution test overrides
HOME/USERPROFILE to a throwaway directory before running anything, so the real
~/.claude is never read or written.
"""

import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "claude-model-router-hook"
INSTALL_PY = PLUGIN_ROOT / "install.py"


def _load_install_module():
    """Import install.py by path (it is not a package member)."""
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


install = _load_install_module()


class TestShellCommand(unittest.TestCase):
    """install._shell_command: the printed form of one hook command line."""

    def test_space_free_paths_are_unquoted(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd = install._shell_command("C:/Python314/python.exe", "C:/x/hook.py")
        self.assertEqual(cmd, "C:/Python314/python.exe C:/x/hook.py")
        self.assertEqual(buf.getvalue(), "")  # nothing needed quoting: no note

    def test_path_with_spaces_uses_call_operator_and_prints_note(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd = install._shell_command(
                "C:/Program Files/Python314/python.exe", "C:/x/hook.py"
            )
        self.assertTrue(cmd.startswith('& "'), cmd)
        self.assertIn("Note:", buf.getvalue())


class TestHookRegistrations(unittest.TestCase):
    """install.hook_registrations derives settings.json entries from hooks.json."""

    def test_against_real_hooks_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            hooks_dir = pathlib.Path(tmp) / "hooks"
            hooks_dir.mkdir()
            raw_spec = json.loads(
                (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
            )
            interpreter = pathlib.Path(sys.executable).as_posix()

            counters = {}
            seen_any = False
            for event, group in install.hook_registrations(PLUGIN_ROOT, hooks_dir):
                seen_any = True
                idx = counters.get(event, 0)
                counters[event] = idx + 1
                orig_group = raw_spec["hooks"][event][idx]
                # matcher/timeout come straight from hooks.json and must survive.
                self.assertEqual(group.get("matcher"), orig_group.get("matcher"))
                for hook, orig_hook in zip(group["hooks"], orig_group["hooks"]):
                    self.assertEqual(hook.get("timeout"), orig_hook.get("timeout"))
                    cmd = hook["command"]
                    self.assertTrue(cmd.startswith(interpreter), cmd)
                    self.assertFalse(cmd.startswith('"'), cmd)
                    entry_name = orig_hook["command"].split(
                        install.PLUGIN_ROOT_TOKEN, 1
                    )[1].strip('"')
                    expected_fragment = hooks_dir.as_posix() + "/" + entry_name
                    self.assertIn(expected_fragment, cmd)
            self.assertTrue(seen_any, "hooks.json yielded no registrations")

    def test_unexpected_command_format_raises_system_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            script_dir = pathlib.Path(tmp)
            (script_dir / "hooks").mkdir()
            bad_spec = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    # Missing the "python3 " prefix hook_registrations requires.
                                    "command": 'python "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"',
                                    "timeout": 5,
                                }
                            ]
                        }
                    ]
                }
            }
            (script_dir / "hooks" / "hooks.json").write_text(
                json.dumps(bad_spec), encoding="utf-8"
            )
            hooks_dir = script_dir / "installed_hooks"
            with self.assertRaises(SystemExit):
                list(install.hook_registrations(script_dir, hooks_dir))


@unittest.skipUnless(
    sys.platform == "win32" and shutil.which("powershell") is not None,
    "PowerShell parse/execution check is Windows-only",
)
class TestPowerShellExecution(unittest.TestCase):
    """Regression test for bug #1: actually run each printed command.

    A quoted interpreter path is a PowerShell ParserError, which a string
    comparison alone would not catch if some other part of the pipeline were
    to reintroduce quoting. This drives real printed commands through real
    PowerShell with a real (copied, temp-dir) entrypoint and router package.
    """

    def test_printed_commands_parse_and_run_under_powershell(self):
        entrypoints = install.entrypoint_files(PLUGIN_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            hooks_dir = tmp_path / "hooks"
            hooks_dir.mkdir()
            for name in entrypoints:
                shutil.copy2(PLUGIN_ROOT / "hooks" / name, hooks_dir / name)
            shutil.copytree(
                PLUGIN_ROOT / "hooks" / "router",
                hooks_dir / "router",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

            # Throwaway HOME so hookio/config module-level expanduser() calls in
            # the child process can never resolve to the real ~/.claude.
            fake_home = tmp_path / "fake_home"
            fake_home.mkdir()
            env = dict(os.environ)
            env["HOME"] = str(fake_home)
            env["USERPROFILE"] = str(fake_home)

            ran_any = False
            for _event, group in install.hook_registrations(PLUGIN_ROOT, hooks_dir):
                for hook in group["hooks"]:
                    cmd = hook["command"]
                    result = subprocess.run(
                        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                        input="{}",
                        capture_output=True,
                        text=True,
                        env=env,
                        cwd=str(tmp_path),  # keep any relative-path reads inside the sandbox
                        timeout=30,
                    )
                    ran_any = True
                    self.assertNotIn(
                        "ParserError", result.stderr, cmd + "\n" + result.stderr
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        cmd + "\nstdout:\n" + result.stdout + "\nstderr:\n" + result.stderr,
                    )
            self.assertTrue(ran_any, "no hook commands were generated to run")


if __name__ == "__main__":
    unittest.main()

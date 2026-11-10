"""Tests for cli_fallback's Windows binary resolution (bug #2).

On Windows the npm shim for `claude` is `claude.cmd`, which a bare "claude"
argv never finds via subprocess without a shell. classify_cli resolves the
binary through shutil.which first, falling back to the bare name only when
which() cannot find it (e.g. offline/sandboxed test environments where PATH
has no claude at all -- fail-open still applies via the existing subprocess
error handling).
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "plugins",
        "claude-model-router-hook",
        "hooks",
    ),
)

from router import cli_fallback  # noqa: E402
from router.cli_fallback import classify_cli  # noqa: E402


def _stub_result(returncode=0, stdout="mechanical"):
    return mock.Mock(returncode=returncode, stdout=stdout, stderr="")


class TestCliBinaryResolution(unittest.TestCase):

    def setUp(self):
        self.cfg = {"classifier": {"cli_fallback": True, "cli_timeout_seconds": 8}}

    def test_uses_resolved_path_when_which_finds_the_shim(self):
        resolved = r"C:\x\claude.cmd"
        with mock.patch.object(cli_fallback.shutil, "which", return_value=resolved), \
             mock.patch.object(cli_fallback.subprocess, "run",
                               return_value=_stub_result()) as run:
            result = classify_cli("rename a file", self.cfg, None)
        self.assertEqual(result, "mechanical")
        args, _ = run.call_args
        argv = args[0]
        self.assertEqual(argv[0], resolved)

    def test_falls_back_to_bare_name_when_which_finds_nothing(self):
        with mock.patch.object(cli_fallback.shutil, "which", return_value=None), \
             mock.patch.object(cli_fallback.subprocess, "run",
                               return_value=_stub_result()) as run:
            result = classify_cli("rename a file", self.cfg, None)
        self.assertEqual(result, "mechanical")
        args, _ = run.call_args
        argv = args[0]
        self.assertEqual(argv[0], "claude")


if __name__ == "__main__":
    unittest.main()

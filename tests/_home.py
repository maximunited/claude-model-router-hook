"""Helpers for isolating tests from the real home directory on all platforms.

On Windows the default temp directory lives under the user profile
(C:\\Users\\<user>\\AppData\\Local\\Temp).  Parent-directory walks in
load_config and project_agent_dirs pass through the real user's
~/.claude, leaking in production config and agent files.

``TempHome`` is a context manager that creates a temporary directory
whose parent chain has no ``.claude`` ancestor, so parent-directory
walks cannot reach the real home.
"""

import json
import os
import pathlib
import shutil
import sys
import tempfile


def patch_home_env(env, home):
    """Set HOME and USERPROFILE in *env* so pathlib.Path.home() and
    os.path.expanduser return *home* on both POSIX and Windows."""
    env["HOME"] = home
    env["USERPROFILE"] = home
    return env


def write_home_sentinel(tmpdir):
    """Create an empty .claude/model-router.json inside *tmpdir*.

    This stops load_config's parent-directory walk at *tmpdir* so it never
    reaches the real user's ~/.claude/model-router.json (which on Windows
    lives under C:\\Users\\<user> and is an ancestor of the default temp
    directory).
    """
    sentinel_dir = os.path.join(tmpdir, ".claude")
    os.makedirs(sentinel_dir, exist_ok=True)
    sentinel = os.path.join(sentinel_dir, "model-router.json")
    if not os.path.exists(sentinel):
        with open(sentinel, "w") as f:
            json.dump({}, f)


# ── Fenced temp directory ─────────────────────────────────────────────────

def _tempdir_is_safe():
    """True when tempfile.gettempdir() has no .claude ancestor."""
    for parent in pathlib.Path(tempfile.gettempdir()).parents:
        if (parent / ".claude" / "model-router.json").exists():
            return False
    return True


def _ancestors_are_clean(path):
    """True when no ancestor of *path* holds a .claude directory."""
    for parent in pathlib.Path(path).resolve().parents:
        if (parent / ".claude").is_dir():
            return False
    return True


def _find_safe_base():
    """Return an existing, writable directory whose ancestors have no .claude.

    Nothing is created here: TempHome makes (and removes) its own directory
    under the returned base, so the suite leaves no trace outside tempdir.
    Order: the normal tempdir when it is already clean; %PUBLIC% (outside the
    user profile, so no ~/.claude above it); the drive root; and as a last
    resort the normal tempdir with a sentinel config at the tempdir level.
    """
    if sys.platform != "win32" or _tempdir_is_safe():
        return tempfile.gettempdir()

    drive = os.environ.get("SYSTEMDRIVE", "C:")
    for base in (os.environ.get("PUBLIC", ""), drive + os.sep):
        if not base or not os.path.isdir(base) or not _ancestors_are_clean(base):
            continue
        try:
            probe = tempfile.mkdtemp(prefix="cmrh-probe-", dir=base)
        except OSError:
            continue
        os.rmdir(probe)
        return base

    # Last resort: use the normal tempdir and write a sentinel.
    tmp = tempfile.gettempdir()
    write_home_sentinel(tmp)
    return tmp


# Lazily computed once per process.
_SAFE_BASE = None


def _safe_base():
    global _SAFE_BASE
    if _SAFE_BASE is None:
        _SAFE_BASE = _find_safe_base()
    return _SAFE_BASE


class TempHome:
    """Context manager returning a temp directory safe from parent-walk leaks.

    Use in place of ``tempfile.TemporaryDirectory()`` for subprocess-based
    tests whose hooks walk CWD ancestors for .claude directories.

    Usage::

        with TempHome() as home:
            _write_home(home, ...)
            _run_hook(..., home, ...)
    """

    def __init__(self):
        self._path = None

    def __enter__(self):
        self._path = tempfile.mkdtemp(prefix="cmrh-home-", dir=_safe_base())
        return self._path

    def __exit__(self, *exc):
        if self._path:
            shutil.rmtree(self._path, ignore_errors=True)
        return False

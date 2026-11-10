"""Best-effort resolution of ladder aliases to concrete model IDs.

The router only ever emits bare aliases (``haiku`` / ``sonnet`` / ``opus`` /
``fable``); Claude Code resolves those to its current default model for each
family, so routing itself never depends on a hard-coded model ID.  The concrete
IDs are informational: they appear in the session advisory text and in tests.

Rather than freeze them at release time, this module discovers the newest
model per family that this machine has actually seen, from local, offline
sources only (no API call, no API key):

1. a static floor (``STATIC_MODEL_IDS``), bumped at release time;
2. IDs recorded in ``~/.claude.json`` by Claude Code itself: the extra model
   option cache and every project's ``lastModelUsage`` table;
3. ``ANTHROPIC_DEFAULT_<FAMILY>_MODEL`` environment overrides, which also pin
   what Claude Code resolves the alias to, so they win outright.

A higher version from any source replaces a lower one.  Mythos IDs are never
accepted (FR-2): the ID grammar only admits the four ladder families.  Every
read is fail-open: a missing or malformed ``~/.claude.json`` yields the floor.
"""

import json
import os
import pathlib
import re

FAMILIES = ("haiku", "sonnet", "opus", "fable")

# Release-time floor. A newer ID discovered locally always wins over this.
STATIC_MODEL_IDS = {
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
    "fable": "claude-fable-5-1",
}

ENV_OVERRIDES = {family: "ANTHROPIC_DEFAULT_" + family.upper() + "_MODEL" for family in FAMILIES}

# claude-<family>-<major>[-<minor>] after suffix stripping. Dated snapshots
# (``@20251001`` / ``-20251001``) and context suffixes (``[1m]``) are cut first.
_ID_RE = re.compile(r"^claude-(haiku|sonnet|opus|fable)-(\d+)(?:-(\d+))?$")
_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")


def parse_model_id(value):
    """``(family, (major, minor), normalized_id)`` for a ladder model ID, else None.

    Accepts aliases with context suffixes and dated snapshots; rejects anything
    outside the four ladder families (so a mythos ID can never parse).
    """
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    for sep in ("[", "@"):
        idx = text.find(sep)
        if idx != -1:
            text = text[:idx]
    text = _DATE_SUFFIX_RE.sub("", text)
    match = _ID_RE.match(text)
    if match is None:
        return None
    family, major, minor = match.group(1), int(match.group(2)), match.group(3)
    version = (major, int(minor) if minor is not None else 0)
    return family, version, text


def _claude_json_path():
    return pathlib.Path.home() / ".claude.json"


def observed_model_ids(claude_json_path=None):
    """Model ID strings Claude Code has recorded locally; empty set on any failure."""
    path = pathlib.Path(claude_json_path) if claude_json_path else _claude_json_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return set()
    if not isinstance(data, dict):
        return set()

    seen = set()
    extra = data.get("additionalModelOptionsCache")
    if isinstance(extra, dict) and isinstance(extra.get("value"), str):
        seen.add(extra["value"])
    elif isinstance(extra, list):
        for entry in extra:
            if isinstance(entry, dict) and isinstance(entry.get("value"), str):
                seen.add(entry["value"])

    projects = data.get("projects")
    if isinstance(projects, dict):
        for project in projects.values():
            usage = project.get("lastModelUsage") if isinstance(project, dict) else None
            if isinstance(usage, dict):
                seen.update(key for key in usage if isinstance(key, str))
    return seen


def resolve_model_ids(env=None, claude_json_path=None, static=None):
    """Alias -> newest concrete model ID known on this machine.

    Never raises and always returns every family: the worst case is the
    static floor unchanged.
    """
    ids = dict(static if static is not None else STATIC_MODEL_IDS)
    versions = {}
    for family, model_id in ids.items():
        parsed = parse_model_id(model_id)
        versions[family] = parsed[1] if parsed else (0, 0)

    try:
        observed = observed_model_ids(claude_json_path)
    except Exception:
        observed = set()
    for raw in sorted(observed):
        parsed = parse_model_id(raw)
        if parsed is None:
            continue
        family, version, normalized = parsed
        if version > versions.get(family, (0, 0)):
            ids[family] = normalized
            versions[family] = version

    env = os.environ if env is None else env
    for family, var in ENV_OVERRIDES.items():
        parsed = parse_model_id(env.get(var))
        if parsed is not None and parsed[0] == family:
            ids[family] = parsed[2]
    return ids

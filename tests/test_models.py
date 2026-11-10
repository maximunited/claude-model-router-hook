"""Tests for router.models: alias -> concrete model ID discovery."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "plugins",
        "claude-model-router-hook",
        "hooks",
    ),
)

from router.models import (  # noqa: E402
    FAMILIES,
    STATIC_MODEL_IDS,
    observed_model_ids,
    parse_model_id,
    resolve_model_ids,
)


def _write_claude_json(payload):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(payload, tmp)
    tmp.close()
    return tmp.name


class TestParseModelId(unittest.TestCase):

    def test_plain_id(self):
        self.assertEqual(parse_model_id("claude-opus-5-5"), ("opus", (5, 5), "claude-opus-5-5"))

    def test_strips_context_suffix_and_snapshot_date(self):
        self.assertEqual(parse_model_id("claude-fable-5-1[1m]")[2], "claude-fable-5-1")
        self.assertEqual(parse_model_id("claude-haiku-4-5@20251001")[1], (4, 5))
        self.assertEqual(parse_model_id("claude-haiku-4-5-20251001")[1], (4, 5))

    def test_major_only(self):
        self.assertEqual(parse_model_id("claude-sonnet-5")[1], (5, 0))

    def test_rejects_mythos_aliases_and_garbage(self):
        for value in ("claude-mythos-5-2", "opus", "fable[1m]", "gpt-5", "", None, 42):
            self.assertIsNone(parse_model_id(value), value)


class TestStaticFloor(unittest.TestCase):

    def test_every_family_has_a_floor_and_no_mythos(self):
        self.assertEqual(set(FAMILIES), set(STATIC_MODEL_IDS))
        for model_id in STATIC_MODEL_IDS.values():
            self.assertNotIn("mythos", model_id)
            self.assertIsNotNone(parse_model_id(model_id))

    def test_missing_claude_json_yields_floor(self):
        ids = resolve_model_ids(env={}, claude_json_path=os.path.join(tempfile.gettempdir(), "nope.json"))
        self.assertEqual(ids, STATIC_MODEL_IDS)


class TestDiscovery(unittest.TestCase):

    def test_observed_ids_from_option_cache_and_usage(self):
        path = _write_claude_json({
            "additionalModelOptionsCache": {"value": "claude-fable-5-2[1m]"},
            "projects": {
                "C:/a": {"lastModelUsage": {"claude-opus-5-5": {}, "claude-haiku-4-5@20251001": {}}},
                "C:/b": {"lastModelUsage": {"claude-mythos-5-2": {}}},
                "C:/c": "not a dict",
            },
        })
        try:
            self.assertEqual(
                observed_model_ids(path),
                {"claude-fable-5-2[1m]", "claude-opus-5-5", "claude-haiku-4-5@20251001", "claude-mythos-5-2"},
            )
            ids = resolve_model_ids(env={}, claude_json_path=path)
        finally:
            os.unlink(path)
        self.assertEqual(ids["fable"], "claude-fable-5-2")  # newer than the floor
        self.assertEqual(ids["haiku"], STATIC_MODEL_IDS["haiku"])  # older stays on floor
        for model_id in ids.values():
            self.assertNotIn("mythos", model_id)

    def test_corrupt_claude_json_is_fail_open(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        tmp.write("{not json")
        tmp.close()
        try:
            self.assertEqual(observed_model_ids(tmp.name), set())
            self.assertEqual(resolve_model_ids(env={}, claude_json_path=tmp.name), STATIC_MODEL_IDS)
        finally:
            os.unlink(tmp.name)

    def test_env_override_wins_even_when_older(self):
        env = {"ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6[1m]"}
        ids = resolve_model_ids(env=env, claude_json_path=os.path.join(tempfile.gettempdir(), "nope.json"))
        self.assertEqual(ids["opus"], "claude-opus-4-6")
        self.assertEqual(ids["sonnet"], STATIC_MODEL_IDS["sonnet"])

    def test_env_override_for_wrong_family_is_ignored(self):
        env = {"ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-mythos-5-2", "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-sonnet-5-5"}
        ids = resolve_model_ids(env=env, claude_json_path=os.path.join(tempfile.gettempdir(), "nope.json"))
        self.assertEqual(ids, STATIC_MODEL_IDS)


if __name__ == "__main__":
    unittest.main()

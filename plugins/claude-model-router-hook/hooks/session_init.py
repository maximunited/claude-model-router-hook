"""
Session init hook: injects model-tier guidance into every conversation,
including mandatory rules for sub-agent model selection.

Cross-platform replacement for session-init.sh.
Adapted from model-matchmaker (https://github.com/coyvalyss1/model-matchmaker)
"""

import json
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    model = data.get("model", "unknown").lower()

    tier_hint = ""
    if "opus" in model:
        tier_hint = " You are currently on Opus. For simple tasks (git ops, renames, formatting), mention that Haiku or Sonnet would be cheaper."
    elif "haiku" in model:
        tier_hint = " You are currently on Haiku. For deep analysis or architecture work, mention that Opus would produce better results."
    elif "sonnet" in model:
        tier_hint = " You are currently on Sonnet. For simple mechanical tasks Haiku is cheaper; for architecture or deep analysis Opus is better."

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "## Model Tier Rules\n\n"
                "These rules apply to YOU and to every sub-agent you spawn.\n\n"
                "### Sub-agent model selection (MANDATORY)\n"
                "When calling the Agent tool, you MUST set the model parameter based on task complexity:\n"
                "- **haiku** — simple mechanical tasks: file searches, grep, glob, reading a handful of files, "
                "git status/log, listing directories, quick lookups. Default for Explore agents unless deep reasoning is required.\n"
                "- **sonnet** — standard implementation: writing/editing code, debugging, creating components, "
                "running tests, most general-purpose agents.\n"
                "- **opus** — architecture decisions, deep multi-file analysis, complex refactors, plan-mode agents, "
                "anything requiring sustained reasoning across large context.\n\n"
                "Never default all sub-agents to Opus. Match the model to the work.\n\n"
                "### Your own tier" + tier_hint + "\n"
                "- Haiku: git ops, renames, formatting, simple edits.\n"
                "- Sonnet: feature work, debugging, planning.\n"
                "- Opus: architecture, deep analysis, multi-system reasoning.\n\n"
                "### Configuration\n"
                "If the user wants to customize routing (keywords, patterns, thresholds), offer to create a config file at "
                "`~/.claude/model-router.json` (global) or `.claude/model-router.json` (project-level). "
                "Project config overrides global.\n"
                "- **thresholds**: `opus_word_count` (default 200), `opus_question_word_count` (default 100), "
                "`haiku_max_word_count` (default 60)\n"
                "- **Per tier** (opus/sonnet/haiku): `mode` (extend|replace), `keywords`, `patterns`, "
                "`remove_keywords`, `remove_patterns`\n"
                "- Mode `extend` (default) merges with built-ins; `replace` discards them.\n"
                "- **action**: `warn` (default) shows a recommendation without switching; "
                "`autoswitch` changes settings.json automatically.\n"
                '- Add `"$schema": "https://raw.githubusercontent.com/tzachbon/claude-model-router-hook/main/'
                'schema/model-router.schema.json"` for IDE validation.'
            )
        }
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()

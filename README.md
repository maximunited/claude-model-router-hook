<div align="center">

# Claude Model Router Hook

**Effort-first model routing for Claude Code. Heuristics-first, opt-in autoswitch.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)
![Shell](https://img.shields.io/badge/shell-bash-blue)

</div>

## Install

```bash
installer="$(curl -fsSL https://raw.githubusercontent.com/tzachbon/claude-model-router-hook/361031c9381fd6d2b5c47b311b7037015b3c2f6d/install.sh)" && bash -c "$installer"
```

The wizard asks whether to install globally and star the GitHub repository. Both prompts default to yes. Installation requires Claude Code and Python 3; starring requires an authenticated `gh` command. Restart Claude Code after installation.

<video src="docs/slides/public/model-router.mov" width="887" controls></video>

Claude Model Router classifies each prompt by task and effort, then recommends the matching Claude model. It warns by default. Autoswitch is opt-in and only affects new sessions.

## What it does

- Routes prompts with local heuristics and an optional Claude Code fallback.
- Uses Haiku only for clearly mechanical work; defaults agentic coding to Opus with graduated effort.
- Routes `Agent` and `Task` sub-agents when they spawn. Nested delegation is floored at the implementation target, and an explicit model always wins.
- Records the requested and resolved model for completed sub-agents, so host-side fallback or allowlist substitutions are visible.
- Dampens borderline classifications instead of switching tiers on weak evidence.

## How it works

| Hook | Job |
|---|---|
| `UserPromptSubmit` | Classifies the prompt and warns or writes the next-session model. |
| `PreToolUse` | Routes `Agent` and `Task` spawns. |
| `PostToolUse` | Logs the model actually used by completed `Agent` and `Task` work. |
| `SessionStart` | Adds the shared task-class rules to each session. |

Errors fail open and leave the prompt unchanged. Prefix a prompt with `~` or `<` to skip routing.

### How model IDs are resolved

Routing itself only ever emits bare aliases (`haiku`/`sonnet`/`opus`/`fable`); Claude Code resolves each alias to its current default model, so routing never depends on a hard-coded model ID.

The SessionStart context also prints an informational "Alias resolution" line mapping each targeted alias to a concrete ID. `hooks/router/models.py` picks the newest ID per family it can find, offline only:

- a static floor (Haiku 5.5, Sonnet 5.5, Opus 5.5, Fable 5.1);
- IDs Claude Code already recorded in `~/.claude.json` (the extra-model-options cache and every project's `lastModelUsage`);
- `ANTHROPIC_DEFAULT_<FAMILY>_MODEL` environment overrides, which win outright.

A higher version from any source replaces a lower one. Mythos IDs are never accepted. Every read is fail-open.

Those same env vars also pin what Claude Code resolves the alias to, not just what this line reports, so a stale `ANTHROPIC_DEFAULT_OPUS_MODEL` in `settings.json` keeps every `opus` spawn on the pinned model until it's removed.

![Sub-agent spawned with the routed model](assets/sub-agent-routing.png)

<!-- advisory:start -->
## Model Tier Rules

These rules apply to YOU and to every sub-agent you spawn.

### Task classes and default targets

| Class | Target model | Effort | When to use |
|---|---|---|---|
| mechanical | haiku | none | Git ops, renames, formatting, lint, file moves, version bumps, quick lookups, short imperative tasks. |
| implementation | opus | medium | Writing or editing code, building features, creating components or APIs, writing tests, standard feature work. |
| debugging | opus | high | Diagnosing failures, flaky tests, races, regressions, stack traces, bisecting, reproducing bugs. |
| architecture | opus | xhigh | Architecture decisions, tradeoff analysis, redesigns, deep multi-file analysis, sustained reasoning over large context. |
| extreme | opus | max | Multi-system migrations, codebase-wide rewrites, long-horizon plans, RFCs and design docs, platform-scale work. |
| abstain | (no routing) | - | Prompt does not clearly match any class; current model and effort pass through unmodified. |

### Sub-agent model selection (MANDATORY)

When calling the Agent tool, set the model parameter to match the task class
above. Do not default every sub-agent to the highest effort. Match the model
and effort to the work: mechanical work goes to haiku, implementation to opus,
debugging to opus, deep analysis to opus, and platform-scale work to opus.
<!-- advisory:end -->

## Configure

Use `~/.claude/model-router.json` globally or `.claude/model-router.json` in one project. Project settings win.

```json
{
  "version": 2,
  "apply_mode": "warn",
  "allow_fable_autoswitch": false,
  "subagent_enforcement": "on",
  "classifier": { "cli_fallback": true },
  "thresholds": { "effort_warn_distance": 2 }
}
```

| Key | Default | Effect |
|---|---|---|
| `apply_mode` | `warn` | Warn or write the model for the next session. |
| `allow_fable_autoswitch` | `false` | Allow autoswitching to an explicitly configured `fable` target. |
| `subagent_enforcement` | `on` | Route, advise, or ignore sub-agent spawns. |
| `classifier.cli_fallback` | `true` | Use `claude -p --model haiku` for ambiguous prompts. |
| `thresholds.effort_warn_distance` | `2` | Warn near a class boundary. |

### Example: opus by default, fable for extreme work, cheaper tiers below

```json
{
  "version": 2,
  "apply_mode": "warn",
  "allow_fable_autoswitch": true,
  "subagent_enforcement": "on",
  "classifier": { "cli_fallback": false },
  "classes": {
    "mechanical": { "target": { "model": "haiku" } },
    "implementation": { "target": { "model": "sonnet", "effort": "high" } },
    "debugging": { "target": { "model": "opus", "effort": "high" } },
    "architecture": { "target": { "model": "opus", "effort": "xhigh" } },
    "extreme": { "target": { "model": "fable", "effort": "high" } }
  }
}
```

- A partial `target` override deep-merges onto the shipped default, so it keeps whatever model or effort it doesn't override.
- The main session is only ever down-routed to haiku, and only past a confidence margin guard. A sonnet `implementation` target therefore changes what model sub-agent spawns get, but an opus session asked for implementation work simply stays on opus at the target effort.
- An `extreme` prompt on an opus session up-routes to fable here (warn mode asks you to run `/model fable` and `/effort high`, then resend).
- Re-run the installer after changing class targets, so the routed-`*` agent files regenerate. The `SessionStart` context warns when a declared variant is missing.

<details>
<summary>Alternative installs</summary>

### Claude plugin manager

```bash
claude plugin marketplace add tzachbon/claude-model-router-hook
claude plugin install claude-model-router-hook@claude-model-router-hook
```

### Manual

```bash
git clone https://github.com/tzachbon/claude-model-router-hook.git
cd claude-model-router-hook
./plugins/claude-model-router-hook/install.sh
```

On Windows (or anywhere without bash), use the Python equivalent (Python 3.10+):

```powershell
py plugins/claude-model-router-hook/install.py       # Windows
python3 plugins/claude-model-router-hook/install.py  # macOS / Linux
```

The printed hook commands use the absolute path of the interpreter that ran the installer (not whatever `python`/`python3` resolves to on `PATH`, which may be the wrong version or the Windows Store alias), and the path is printed unquoted on purpose: Claude Code on Windows runs hook commands through PowerShell, where a line starting with a quoted string is a ParserError, so a quoted interpreter path would break every hook. If Python or `~/.claude` lives under a path with spaces, the installer instead prints the PowerShell call-operator form (`& "..."`) and a note; move Python to a space-free path on that host instead.

The manual installer prints the `settings.json` entries that you need to add.

</details>

## Notes

- Activity is logged at `~/.claude/hooks/model-router-hook.log`, including requested versus resolved sub-agent models.
- If another `PreToolUse` hook rewrites the same spawn, Claude Code's undocumented merge order decides which rewrite wins.
- Prefix a prompt with `~` to bypass routing for that prompt only; it's logged as `OVERRIDE`.
- In warn mode, a mismatch blocks the prompt with a message like `Run /model X and /effort Y, then resend`, until you switch or bypass with `~`. It never changes the running session itself.
- Autoswitch writes `~/.claude/settings.json` for new sessions only; it still asks you to run `/model` to apply the change to the current one.
- `max` effort is session-only, so autoswitch persists `xhigh` instead and says so in its message.

## Project

[Contributing](CONTRIBUTING.md) | [MIT license](LICENSE) | Based on [model-matchmaker](https://github.com/coyvalyss1/model-matchmaker) by [@coyvalyss1](https://github.com/coyvalyss1)

# User-selected Hermes model lanes

## Purpose

Use this reference when the user asks to inspect or switch the Hermes model list.
The repository provides provider-family entry points, but it does **not** define a
default model, a default picker, or a preferred model for the user.

## Provider lanes

| Entry point | Hermes provider | Model selection | Ownership |
|---|---|---|---|
| `deepseek` / `dp` | `deepseek` | `--model MODEL` or `HERMES_DEEPSEEK_MODEL` | User |
| `gpt` / `chatgpt` | `openai-codex` | `--model MODEL` or `HERMES_GPT_MODEL` | User |

The provider and model values are written only after an explicit user command.
The script fails closed when a model ID is missing; it never guesses a model.

## User-owned picker and aliases

The portable overlay intentionally does not write `model_picker`, `quick_commands`,
Provider routes, or model IDs. If the user has configured Hermes picker lanes or
slash aliases through the official Hermes entry point, those values remain user-
owned and must not be replaced by this repository.

A user-owned alias may target a selected model, for example:

```yaml
quick_commands:
  切换deepseek:
    type: alias
    target: /model <user-selected-model> --provider deepseek
    description: User-selected DeepSeek model
```

Do not convert these aliases into shell `exec` commands. Keep them inside Hermes'
own `/model` handler so session state, confirmation, and UI behavior stay consistent.

## Explicit switch commands

Run from the WORK-LAB repository root:

```bash
python integrations/executors/hermes/switch_model.py status
python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL"
python integrations/executors/hermes/switch_model.py gpt --model "$HERMES_GPT_MODEL"
```

`--live` is opt-in and may consume provider quota. Switching does not mutate an
in-flight session; start a new session or run `/reset` afterward.

## Verification contract

After each switch, do not claim success from config alone. If the user requests
execution proof, run a small `hermes chat -q` marker through the explicitly
selected provider/model and report the marker plus the redacted provider/model
summary. Marker text must be unique to that run; old benchmark markers are not
proof for a future session.

## Desktop picker click caveat

If a model picker click appears to do nothing while a turn or tool run is active,
check whether the session is busy. The backend may reject a hot switch during an
in-flight turn. Interrupt or wait for the turn, then apply the user's explicit
`/model <selected-model> --provider <selected-provider>` command, or start a new
session. A UI must keep the picker open when the asynchronous switch returns a
busy-session rejection; it must not claim that the model changed.

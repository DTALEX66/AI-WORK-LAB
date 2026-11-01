# GPT OAuth Token Recovery

When Hermes reports `HTTP 401: Encountered invalidated oauth token for user` for
`openai-codex`, the OAuth credential held by **Hermes** has been revoked or
expired. CC Switch being connected only proves its own route is available; it
does not prove Hermes has a usable OAuth credential.

## Safe recovery boundary

Do **not** read, print, copy, parse, or import `~/.codex/auth.json`, Hermes
`auth.json`, browser cookies, Windows Credential Manager entries, access tokens,
or refresh tokens. A ChatGPT OAuth token is not an OpenAI API key.

Use Hermes' supported credential flow instead:

```bash
hermes auth add openai-codex
```

Complete the device-code/browser login in the user's browser. Then start a new
Hermes session or run `/reset`.

## Verify after re-authentication

A port check or successful config write is not proof of inference. Run one
small, real marker request:

```bash
hermes chat --provider openai-codex -m "$HERMES_GPT_MODEL" \
  -q "Reply exactly: GPT-OAUTH-LIVE-OK" -Q --toolsets safe
```

Only report recovery when the process exits `0` and prints the exact marker.

## Common states

| State | Meaning | Action |
|---|---|---|
| `token_revoked` / HTTP 401 | Hermes OAuth credential is invalid | Run `hermes auth add openai-codex` |
| CC Switch connected, Hermes 401 | Network route works; Hermes auth does not | Re-authenticate Hermes; do not copy tokens between stores |
| Device flow waiting | Browser authorization is pending | Complete it in the user's browser; do not kill/restart the command blindly |
| Fresh auth but current chat still errors | Existing session/client is frozen | `/reset` or start a new chat, then rerun the marker |

## Pool maintenance

`hermes auth list openai-codex` is an inventory view only. It does not prove a
credential can infer. Do not edit the credential pool files directly; use
Hermes auth commands so refresh and revocation state remain consistent.

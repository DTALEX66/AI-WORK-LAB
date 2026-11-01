# Hermes MCP Hardening Pattern — 2026-07

Use this reference when upgrading Hermes/Codex/CC Switch workflow packs or adding MCP servers to a portable repo.

## Trigger

A post-push independent review flagged that default MCP config used floating npm packages and that diagnostic scripts could under-redact credentials. The correct response was a follow-up hardening commit, not a passive note.

## Durable pattern

1. **Pin MCP packages before default enablement.**
   - Query current version with `npm view <package> version` using the trusted Node/npm runtime.
   - Put `package@<verified-version>` in config and docs.
   - Keep `latest` only as prose warning text, not as a copy-pastable command.

2. **Use a trusted Node wrapper.**
   - Prefer the Hermes bundled Node when the deployment owns it.
   - Do not silently fall back to PATH `npx`; PATH fallback must be explicit and Node-major-version checked.

3. **Document network/trust boundaries.**
   - Context/documentation MCPs may send package names or queries to external services.
   - State that private code, customer data, and secrets must not be used as query text.

4. **Harden diagnostic output.**
   - Redact Bearer tokens, JWTs, GitHub tokens (`ghp_`, `github_pat_`), npm tokens, Slack `xox*` tokens, OpenAI-style `sk-` keys, OAuth access/refresh/id tokens, generic API keys, secrets, and passwords.
   - Add a tiny redaction regression probe in verification.

5. **Respect async review results.**
   - If an async/subagent code review returns after push with `passed=false`, resolve its findings in a follow-up commit and rerun verification.

## Verification commands to adapt

```bash
python3 -m py_compile scripts/workflow/*.py scripts/security/*.py
bash -n setup.sh
bash -n bin/hermes-npx
python3 packages/client-neutral-core/scripts/security/scan_agent_rules.py templates skills docs scripts bin
grep -RInE '@latest|gpt-4o|--json' README.md config docs scripts skills bin setup.sh setup.ps1 templates || true
hermes mcp test context7
hermes mcp test context7

The grep should return no unintended copy-pastable stale examples; if it intentionally matches a warning phrase, rewrite the phrase to avoid a literal risky command.

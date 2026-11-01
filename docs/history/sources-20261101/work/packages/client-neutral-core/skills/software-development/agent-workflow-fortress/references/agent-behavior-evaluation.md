# Agent Behavior Evaluation Absorption

Workflow-assistance absorbs promptfoo-style agent behavior evaluation as a **method**, not as a default runtime dependency.

## Source

- Upstream idea: `promptfoo/promptfoo`
- Absorbed form: declarative case layout, expected markers, negative claims, CI-friendly YAML shape
- Runtime assets: none
- Default provider/model: none

## Boundaries

Do:

- Keep eval templates model/provider neutral.
- Use placeholders for provider and prompt.
- Store run artifacts under project-local `.hermes/task-artifacts/evals/`.
- Test global Hermes Agent + CC Switch + Codex workflow boundaries: repo/live/session layering, Gateway delivery layering, busy queue vs durable execution, interrupted delegation evidence, PowerShell selection, verification honesty, and secret handling.

Do not:

- Commit real provider credentials, traces, private prompts, raw request dumps, headers, sessions, logs, or cache files.
- Default-install promptfoo or any hosted evaluation/observability service.
- Treat eval success as proof that tools, MCP, live provider execution, exact-tree review, or CI passed.

## Local artifacts

- `docs/workflow/agent-evaluation.md`
- `templates/evals/agent-behavior-smoke.yaml`

# Local Quality Gates

Workflow-assistance uses the Python runner as the canonical local quality gate.
The optional `Justfile` is only a convenience wrapper; just is not a required dependency.

## Canonical command

```bash
python services/orchestration/run_quality_gate.py verify
```

The runner first performs a fail-fast dependency preflight from
`requirements.txt`, then runs the registered client-neutral gates in order. CI
resolves the same direct constraints through hash-locked `requirements.lock`
with `--require-hashes`; regenerate the lock deliberately when direct
constraints change.

The gate list is dynamic — the machine registry is the single source of
truth. Discover the current gate set and counts with:

```bash
python services/orchestration/run_quality_gate.py list
```

Do not treat any gate count written in this document (or any other doc) as a
permanent norm; counts grow as gates are added. Representative gates in the
current registry include `governance`, `compile`, `skill-provenance`,
`security`, `context-pack`, `client-neutral-manifest`, `core-schemas`,
`adapter-registry`, `adapter-conformance`, `acp-conformance`, `otel-mapping`,
`usage-ingestion`, `memory-contamination`, `task-ledger-replay`,
`portable-install`, `provider-inventory`, `mcp-audit`, `shell`,
`runtime-convergence`, `powershell` — run `list` above for the live set
rather than relying on any hard-coded number.

`portable-install-runtime` remains registered as an explicit optional Adapter
compatibility gate. It is not part of default `verify`, and core CI must not
install or pin Hermes solely to make it run.

The runner stops on the first failure with
`QUALITY_GATE_FAIL gate=<name> exit_code=<code>` and prints the complete gate
list only after every required gate passes as
`QUALITY_GATE_PASS gates=<ordered-required-gates>`.

## Individual gates

Use `python services/orchestration/run_quality_gate.py list` to discover the current
registry, then run a gate by name, for example:

```bash
python services/orchestration/run_quality_gate.py adapter-conformance
python services/orchestration/run_quality_gate.py runtime-convergence
python services/orchestration/run_quality_gate.py portable-install-runtime
```

## Platform and data boundaries

- `shell` and `powershell` perform syntax/AST checks and explicitly skip when
  their supported tool is unavailable.
- Generated reports stay under ignored `.project-local/artifacts/` or
  `.project-local/runs/` paths.
- `portable-install` uses only an isolated empty Home.
- `portable-install-runtime` requires an already capability-discovered runtime.
- No gate reads `.env`, auth stores, session databases, prompts/responses,
  private memory bodies, credentials, or live secrets.

GitHub Actions invokes the same runner after installing `requirements.txt` so
local and CI contracts remain aligned. Local PASS is not exact-SHA CI evidence.

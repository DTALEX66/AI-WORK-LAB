---
name: autonomous-evaluation-fallback
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/autonomous-evaluation-fallback/SKILL.md
---

---
name: autonomous-evaluation-fallback
description: Build trace redaction and local evaluation for agent loops.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [evaluation, trace, redaction, security, autonomous-loops, verification]
    related_skills: [agent-workflow-fortress, sleep-mode, project-data-boundary]
---

# Autonomous Evaluation Fallback

Build secure, model/provider-neutral evaluation and trace redaction for autonomous agent loops. Use when the agent needs to evaluate its own execution traces, redact secrets before persisting them, or produce project-local evaluation artifacts — all without calling an external model or API.

## When to Use

- Implementing a `K-001`-style evaluation/trace + redaction module in an autonomous loop
- An agent needs to self-evaluate without model access
- Traces contain API keys, tokens, passwords, or paths that must not leak to disk
- Designing a local fallback for a product's evaluation pipeline

## Core Pattern: Layered Redaction

Structure redaction in three independent, ordered layers:

```
Layer 1 — Key-name detection
  Scan dict key names for {"api_key", "token", "secret", "password",
  "jwt_secret", "credential", ...}. Replace entire value with "[REDACTED]".
  Always fires first — independent of value content.

Layer 2 — Value regex patterns
  Apply regex patterns grouped by category (API keys, paths, SSH keys,
  cookies, connection strings). Gate each category by a boolean policy flag.
  Multi-line patterns (SSH keys, PEM blocks) need [\s\S] + re.DOTALL.

Layer 3 — Content-length truncation
  For content-hosting keys ("content", "body", "text", "raw"), truncate
  beyond a configurable max length. Separate from generic truncation to
  avoid false positives on short diagnostic values.
```

## Regex Redaction Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Multi-line PEM/SSH keys | Regex silently skips the value | Use `[\s\S]+?` and `re.DOTALL` flag |
| Pattern filter mismatch | Pattern never fires because its replacement doesn't match gate keyword | Gate on `"PRIVATE"` or `"KEY"` in the replacement, not just `"SECRET"` / `"AWS"` |
| Raw value vs JSON pattern | Content field > 200 chars not redacted | Use key-name detection (Layer 1) or content-length check (Layer 3), not JSON-style regex |
| Windows path difference | `/home/user/` regex misses `C:\Users\user\` | Add separate path patterns per OS |
| Nested dict/list traversal | Secrets in nested objects survive | Recursively visit all levels with depth limit (recommended: 10) |

## Hash Audit Trail

Compute sha256 **before and after** redaction to prove no secrets leaked:

```python
original_hash = hashlib.sha256(
    json.dumps({"events": e, "result": r}, default=str, sort_keys=True).encode()
).hexdigest()
# ... redact in place ...
redacted_hash = hashlib.sha256(
    json.dumps({"events": e, "result": r}, default=str, sort_keys=True).encode()
).hexdigest()
```

Store both hashes in the output struct and every evaluation artifact. When `original_hash != redacted_hash`, secrets were stripped. The artifact reader can verify that no raw secret made it to disk.

## Local Evaluation Dimension Inference

Without a model, infer dimension status from event metadata alone:

| Dimension | Passed | Failed | Unverified |
|---|---|---|---|
| **evidence** | at least one `ok` event | any `error`/`blocked` event | no events |
| **completeness** | result has all expected keys | result missing all expected keys | partial key match |
| **safety** | no `high`-risk events | any `high`-risk event | — |
| **correctness** | result.success in (true, "done", "completed") | result.success in (false, "failed", "blocked") | no result success field |
| **efficiency** | total duration < 10s | total duration > 60s | 10-60s |
| **maintainability** | — | — | always unverified (needs code review) |
| **knowledge_contribution** | — | — | always unverified (needs lesson extraction) |

**Important:** Label all inferences explicitly as "local fallback, no model/API used." Never conflate with accuracy or model-graded metrics.

## Artifact Writing Discipline

- Write to project-local ignored path: `.hermes/task-runtime/evaluation/`
- Every artifact must include redaction metadata (`redacted_fields`, `original_hash`, `redacted_hash`, `wrote_secrets`)
- Never write raw secrets — only hash audit trail proves what was removed
- Include `schema_version` for replay/validation
- Use ISO-8601 timestamps and deterministic filenames

## Replay Pattern

```python
def replay_evaluation(artifact_path: str | Path) -> EvalResult | None:
    path = Path(artifact_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("schema_version") != EXPECTED_VERSION:
        return None
    # ... reconstruct dimensions and events ...
```

## Schema/Contract Validation

Validate artifacts before trusting them:

```python
def validate_evaluation_schema(data: dict) -> list[ContractFailure]:
    failures = []
    for key in ["success", "score", "failure_reason", "improvement"]:
        if key not in data:
            failures.append(ContractFailure(field=key, ...))
    # Type checks: success=bool, score=(float|int), dimensions=dict, events=list
    # Dimension status must be one of {"passed", "failed", "unverified"}
    return failures
```

## Model/Provider Neutrality Rules

- No Pydantic dependency — use `@dataclass(frozen=True)`
- No external API or model calls
- No model inference
- Default output: local, desensitised, project-artifact-bound
- Policy objects as frozen dataclasses with boolean flag toggles
- All types self-contained in the module (no imports from product `app/` or `knowledge_base/`)

## Verification Checklist

- [ ] Each secret type (API keys, tokens, passwords, paths, SSH keys, cookies, URLs) has its own test
- [ ] Multi-line secrets are tested and use DOTALL
- [ ] Custom policy can disable each redaction category independently
- [ ] Hash audit trail proves secrets were stripped
- [ ] No Pydantic / model / API dependencies
- [ ] Artifact writes under project-local `.hermes/task-runtime/evaluation/`
- [ ] Replay handles missing, corrupted, and wrong-schema files gracefully
- [ ] Schema validation rejects wrong-types and missing keys
- [ ] Full pipeline test: redact → evaluate → write → replay → validate

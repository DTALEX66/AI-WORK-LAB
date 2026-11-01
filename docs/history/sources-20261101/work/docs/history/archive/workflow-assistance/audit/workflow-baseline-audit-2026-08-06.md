# Workflow baseline and live-overlay audit — 2026-08-06

## Scope and positioning

This audit treats WORK-LAB as the client-neutral control plane and
`10-workflow/workflow-assistance` as its portable workflow enhancement module.
Hermes, Codex, credentials, sessions, caches, user-installed skills and live
mixed-ownership configuration remain external platform state. They are checked
only through redacted status, exact managed-asset hashes or official validation
commands; they are not copied back into this repository.

## Baselines

- WORK-LAB cloud and local baseline agreed at `4b8e03431821dbd104ba4e2e1e77c03d1824fa65`
  before this audit batch.
- Hermes official upstream baseline was
  `863e31318553cda8ad61df681d08175364d4164b` (`v0.20.0`).
- The Windows project-handle correction remains a clearly separated carried
  patch and Draft upstream PR: `NousResearch/hermes-agent#80344`.
- Codex global guidance was semantically identical to
  `templates/agent-rules/CODEX_GLOBAL_AGENTS.md`; the only byte difference was
  platform newline encoding.

## Findings and fixes

| Area | Finding | Resolution |
|---|---|---|
| Managed Hermes assets | All 13 managed skill roots, 6 launchers/guards, `SOUL.md` and `.env.template` matched repository source exactly. | No live copy was required. User and bundled skills outside those exact roots were preserved. |
| Hermes plugins and skills | Required `security-guidance` and `web-ddgs` plugins were enabled. Hermes reported 124 enabled skills and none disabled. Seven bundled skills marked user-modified correspond to repository-owned workflow overlays. | Kept the official/runtime/user layering; no bulk reset or reverse copy was performed. |
| Terminal safety Hook | The deployed guard matched source but its consent record referenced an earlier file revision. | Revoked only the exact old consent entry, re-approved the current script through the official `--accept-hooks` path and obtained a clean `hermes hooks doctor`. |
| Portable sync boundary | Documentation said live `config.yaml` was never promoted, while `deploy_portable()` still defaulted to `include_config=True`. The ActionPlan also advertised a merge and hashed the mixed-ownership file. | Default and CLI deployment now force `include_config=False`; ActionPlan reports `skip_mixed_ownership` and records existence/type only. Isolated verifier construction remains explicitly available with `include_config=True`. |
| Installer dependency | Setup required PyYAML but checked only that Python executed, producing a late and opaque failure on a clean interpreter. | PowerShell and Bash setup now fail before Home writes unless `PyYAML>=6,<7` is present; setup remains plan-first and never auto-installs into a global interpreter. |
| Hermes Git baseline | An inactive local `main` belonged to an obsolete shallow-history lineage and had no merge base with official `main`. | Preserved the old tip under a local recovery ref, then aligned inactive `main` to official upstream. The runtime branch remains official upstream plus the single reviewed carried patch. |
| Windows lock diagnosis | Running `diagnose-lock` from the target made the diagnostic process itself participate in the lock and could recommend Hermes cleanup when only a shell/Codex process owned the CWD. | Upstream PR now probes from an existing safe CWD without creating directories, restores CWD in `finally`, excludes its own PID and distinguishes Hermes holders from non-Hermes callers. |
| Project data hygiene | One old ignored log had a flattened root filename and a root `.pytest_cache` predated the current boundary. | Moved the unread log into project-local `.project-local/runs/logs/`; removed only the confirmed non-link regenerable pytest cache. |

## Verification

- Workflow-assistance canonical quality gate: PASS; 193 governance tests passed,
  5 explicitly skipped, and all configured structural sub-gates returned zero.
- ActionPlan/sync focused regression: 6/6 PASS.
- Open Design structural and contract verifier: PASS, including
  `203/203`, `223/223`, `10/10` and aggregate `460/460` results.
- WORK-LAB Observer: structure PASS and 3/3 tests PASS.
- Root integration: contract catalog `20/20`, module registry `3` with
  `runtime_edges=0`, project data boundary, supply-chain pins, sanitized error
  ledger, and 12 root governance tests all PASS.
- Hermes upstream lock/CLI regression: 13/13 PASS; native Windows
  DELETE_SHARE probe PASS on an isolated project-local directory.
- Live Hermes config schema check and Hook doctor: PASS.
- GitHub CLI authorization and the connected GitHub integration were present;
  no token value or credential store was read or recorded.
- External Context7 live testing is not claimed: the attempted external MCP
  smoke was blocked before execution because its outbound payload was not
  separately approved by the execution policy. Static MCP/package governance
  remained covered by the local quality gate.

## Operating model after the audit

1. Update Hermes from the official upstream baseline.
2. Carry the smallest reviewed patch only while its upstream PR is unmerged.
3. Deploy only the exact repository-owned portable roots into Hermes Home.
4. Change mixed-ownership live configuration only through official Hermes
   commands and explicit user review.
5. Keep bundled and user-installed skills/plugins outside repository ownership
   unless a separate provenance-reviewed absorption task approves them.
6. Before every upstream push, scan the entire candidate diff and PR metadata
   for local paths, usernames, credentials, auth/config files and private logs.

No provider route, model choice, credential, session, prompt/response body,
private skill content or personal filesystem path was added to the repository or
the upstream Hermes PR.

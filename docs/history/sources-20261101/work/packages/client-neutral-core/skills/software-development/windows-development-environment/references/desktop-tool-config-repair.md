# Desktop tool config drift + diagnostic-script staleness (validated 2026-08-12)

Scenario: configuring a locally-installed desktop tool (Open Design / Codex /
OpenHuman) whose `doctor` / `configure` diagnostic reports FAIL, and you must
decide whether the FAIL is a real config problem or the script's own stale
expectation before touching anything.

## Core rule: a diagnostic FAIL may be the TOOL's expectation, not the config

Before "fixing" the config, verify the FAIL is a genuine config problem. The
two concrete staleness bugs observed:

1. **Hardcoded expected value vs actual.** `doctor` had
   `DEFAULT_MODEL = "gpt-5.6-terra"` hardcoded, but the tool's `app-config.json`
   actually carried `gpt-5.6-luna`. The FAIL was a stale script constant, not a
   misconfiguration — the user's actual model was authoritative and the script
   was out of date. Fix the script constant AND the unit test that asserted the
   old constant in the SAME commit (the test hardcoded `DEFAULT_MODEL = "...terra"`).

2. **Configured path returned without existence check.** `find_codex_bin` read
   `agentCliEnv.codex.CODEX_BIN` from config and returned it verbatim even when
   that path no longer existed (the Codex versioned dir was removed by an
   upgrade). The real Codex lived under a different versioned dir
   (`bin/<sha>/codex.exe`). Fix: verify `Path(configured).exists()` before
   returning; otherwise fall through to `glob("*/codex.exe")` sorted reverse.

## Safe repair sequence

1. **Diagnose read-only first.** Run `doctor` and `configure --project-root <exact>`.
   The `configure` script is PLAN-ONLY (never writes private config/launchers) —
   it only reports detected paths/version/auth. Use it to learn the truth
   (actual Codex exe, version) without mutating anything.
2. **Back up the private config before editing it.**
   `cp <app-config.json> <project>/.hermes/task-runtime/app-config.json.bak-<date>`.
3. **Read only the structure-relevant fields, never secrets.** Dump
   `agentCliEnv.codex.CODEX_BIN`, `agentModels.codex.model`,
   `defaultProjectLocationId`, and `projectLocations` ids — skip any auth/token
   subtree. This confirms what the tool actually believes.
4. **Verify the candidate replacement binary runs** before pointing the config
   at it: `"<path>/codex.exe" --version`. Pick the real existing versioned exe,
   not a guess.
5. **Edit the private config surgically** — change ONLY the drifted field
   (`CODEX_BIN`), preserve model/auth/locations/other keys. Use a JSON
   load-modify-dump with `indent=2` (preserves structure); re-validate JSON.
6. **Fix the diagnostic script + its test assertion together** (one commit),
   not just the config: update the stale constant, add the path-existence guard,
   sync the hardcoded test expectation. Run the full test suite — the test will
   fail until the assertion is updated.
7. **Rerun `doctor`** to confirm the formerly-FAIL checks now PASS. Remaining
   FAILs that are self-inflicted (you edited the doctor script, so
   `repo is clean` FAILs) clear once you commit.

## Evidence-location pitfall for capability/evidence claims

When a taskpack claims an E3/E5 evidence file "is not in the repo", search ALL
tracked evidence locations before concluding it is absent — not just the
obvious `.hermes/task-runtime/`. In this repo the live Axe scan lived under
`opendesign-assistance/domain-packs/uiux-design/evidence/` (tracked, committed
in the merged taskpack). A quick `git ls-tree -r origin/main --name-only | grep
-iE 'axe|evidence'` avoids a false "evidence missing" downgrade. This matters
for the capability-evidence-index: only downgrade a capability's E-level if you
can prove the runtime evidence is genuinely absent, not just not-where-you-looked.

## Guards
- `configure_open_design_windows.py` is intentionally PLAN-ONLY (ODA4-0112
  shrank it to read-only diagnostics; `WRITE_SET=[]`). Respect that boundary —
  it never writes private config or launchers. Actual private-config writes are
  only the surgical, backed-up, user-authorized CODEX_BIN/model fix.
- Never read or print auth tokens / credentials in `app-config.json`.

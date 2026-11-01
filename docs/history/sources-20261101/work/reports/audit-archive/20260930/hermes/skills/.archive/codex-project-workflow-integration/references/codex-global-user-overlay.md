# Codex global user overlay: validated pattern

## Scope

Use only when the user explicitly requests Codex behavior across arbitrary projects. A project-local `AGENTS.md` or skill is insufficient evidence for this claim.

## Owned surfaces

A safe user-layer package may own only:

1. one marker-delimited block in `$CODEX_HOME/AGENTS.md`;
2. exact, uniquely prefixed skill roots in `$HOME/.agents/skills/`;
3. one exact rules file in `$CODEX_HOME/rules/`;
4. a small allowlist of top-level defaults in `$CODEX_HOME/config.toml`, written only when absent;
5. a non-secret ownership state containing version, exact target names, and hashes.

Preserve provider, model, base URL, authentication, MCP, plugins, sessions, Desktop state, sandbox internals, unrelated guidance, and unrelated skills. Never archive the full mixed-ownership config merely to simplify rollback.

## Lifecycle contract

Implement four explicit operations:

- `plan`: preflight and print only bounded actions and field names; no secret-bearing values or file bodies.
- `apply`: fail on unowned same-name targets, write exact owned assets, parse config after mutation, record ownership, then verify.
- `verify`: require a supported state version, exact managed block content, exact rules/skill hashes, and parsed expected config values.
- `rollback`: require valid ownership state and matching current hashes; remove only owned blocks/fields/files. Drift blocks rollback instead of deleting user changes.

Idempotent apply and rollback must be tested in an isolated home before touching the real user layer.

## Mixed-ownership TOML editing

TOML table scope is positional: a key appended after `[mcp_servers.example]`, `[projects."..."]`, or any other table belongs to that table rather than the document root. For top-level managed defaults:

1. remove the package's prior marker-delimited block;
2. parse the remaining document and preserve every existing key/table;
3. identify which allowlisted top-level fields are genuinely absent;
4. insert the managed block before the first table header, not at end-of-file;
5. parse the rendered TOML again and selectively read back only the managed fields and non-secret identity fields.

For a strict parser smoke, use a Codex command shape that actually supports strict config, such as `codex --strict-config exec --help`. Do not infer that strict parsing failed merely because an unrelated subcommand (for example `features`) rejects that global option.

## Persistent-state evolution

The state file is part of the public recovery contract. When adding a required field:

1. keep the old reader compatible or implement a versioned migration;
2. add fixtures for every deployed state version;
3. test `old state → plan → migrate/apply → verify → rollback → reapply`;
4. deploy the reader and migration together;
5. do not overwrite the old state until the migrated state and live assets have been verified;
6. rerun the final quality gate after the migration code is the final tree.

A reader that rejects the currently deployed state can disable verification and rollback even while Codex itself still loads the already-installed assets. Treat that as incomplete maintenance tooling, not a successful configuration closure.

## Adversarial ownership and recovery controls

Run these probes only in isolated temporary Codex/agent homes, never against the live user profile:

1. **Managed-block drift:** after apply, change one managed config value and add an unrelated user key/table inside the marker block. Both re-apply and rollback must fail closed while preserving the edited bytes. Validate the exact canonical managed block (or its hash), not only marker counts and expected keys; otherwise rollback can delete a provider/model/MCP/plugin field that a formatter or user moved inside the comments.
2. **Complete-config TOCTOU:** pause after preflight, change representative provider/model, MCP, plugin, and unknown future fields in the live config, then resume at the real atomic replace. The replace must compare the complete original bytes immediately before publication and preserve the concurrent version on mismatch. A cooperative operation lock alone does not exclude Codex Desktop or another config writer.
3. **Interrupted lifecycle:** inject failure after every apply and rollback mutation. Recovery must be resumable or restore all earlier mutations. A first apply that leaves markers without ownership state, or a rollback that leaves state pointing to already-deleted targets, is release-blocking even when every happy-path test passes.
4. **Skill-set evolution:** diff the previous state's exact managed skill names against the current source manifest. Retire an old target only while its current hash still matches recorded ownership, and do not drop ownership until retirement succeeds. Conversely, a newly introduced source name with no previous ownership hash must not adopt an exact same-name user target merely because its bytes match. Verify must bind state names and hash keys to the exact owned set, and rollback must leave no owned residue.
5. **Windows path redirection:** place `rules/` and `.agents/skills/` behind disposable junction/reparse ancestors and prove plan/apply/rollback cannot escape the declared roots. Validate every existing descendant from the declared root to the leaf—not just `leaf.is_symlink()`—because a regular-looking child below a directory junction already resolves outside the boundary. Either reject redirected descendants or document and test an explicit logical-root policy; silently following a junction to another user tree is not path-boundary proof.

Keep these as negative controls through the real orchestration entry point. Mocking only the renderer or planner does not exercise the mutation linearization point.

## Two-phase ownership journal pattern

For a multi-file overlay, writing ownership state last is unsafe: an interrupted first apply can leave managed markers or directories with no state, disabling safe rollback. Use a two-phase, non-secret ownership journal:

1. Preflight the complete target set and capture the full bytes of every mixed-ownership file plus hashes of exact-owned files/directories.
2. Build the desired final state, then atomically publish `phase: applying` **before** any managed target mutation. The pending state records:
   - desired managed-block and target hashes;
   - previous managed-block and target hashes;
   - the union of current and retiring owned skill names;
   - field names and ownership metadata only, never config bodies or secret values.
3. At each mixed-ownership replace, compare the complete current bytes with the preflight bytes immediately before `os.replace`; an advisory operation lock is supplementary and must not substitute for this comparison.
4. For exact-owned skills/rules, re-check the current hash at the mutation point. Remove a retired target only while it still matches its previous ownership hash; do not drop its name from ownership before removal succeeds.
5. After all mutations and readback pass, atomically replace the pending journal with `phase: applied` whose target-name and target-hash sets are exact and complete.
6. Pending rollback accepts only three proven states per target: absent because the mutation had not happened, the recorded previous hash, or the recorded desired hash. It removes only matching assets/blocks and rejects any fourth state. Applied rollback remains stricter: required owned targets must exist and match.
7. Journal rollback itself before its first deletion. Atomically move the state to `phase: rolling_back`, keep that state until every owned target is removed, and make a retry accept only absent, previous-hash, or desired-hash states. Without this phase, a failure after removing a rule or the first skill can leave an `applied` state that rejects recovery because required targets are already missing.

Keep regression probes for managed config drift, managed guidance drift, an extra user field placed inside a managed block, complete-config TOCTOU, failure after the first mixed-ownership write, failure after the first rollback deletion, legacy-state migration, and retired-skill cleanup. The mixed-ownership fixture should contain representative provider, model, base URL, MCP, plugin, and unknown future fields so apply/rollback proves all user-owned namespaces survive byte-safe replacement. Run probes through the real `apply`/`rollback` entry points in isolated temporary homes. A happy-path idempotence test alone does not prove transactional recovery.

## Command-policy controls

Use `codex execpolicy check` against the installed rules file with both controls:

- destructive command expected to be `forbidden`;
- every force-push spelling promised by the contract—including `--force`, `-f`, `--force-with-lease`, and `--force-if-includes`—has an explicit negative control rather than falling through to the generic push prompt;
- normal publication command expected to be `prompt`;
- read-only query expected to have no blocking match.

Prefix policies are position-sensitive. If the policy language cannot reject a dangerous flag in every argv position, do not overstate the rule as a complete force-push prohibition; pair it with repository instructions and explicit approval controls or use a wrapper that can inspect the full argv.

Rules complement rather than replace sandboxing, project instructions, and explicit user approval.

## Arbitrary-project canary

Create a minimal, separate Git root that cannot inherit project-local rules from the source repository. Start a fresh real Codex task and ask it—without providing exact skill file paths—to report:

- default user-facing language;
- checkout writer ownership rule;
- whether global config may be changed without exact authorization;
- completion evidence states;
- all visible uniquely prefixed user skills and paths.

Also run one harmless default-mode canary and inspect the runtime header to prove the effective sandbox. Non-interactive `codex exec` may report `approval: never` according to command semantics; use parsed config readback to verify an interactive `on-request` default.

## Evidence classification

Report separately:

```text
USER_OVERLAY_STRUCTURAL
USER_OVERLAY_LIVE_DISCOVERY
ARBITRARY_PROJECT_CANARY
ROLLBACK_READBACK
MODEL_PROVIDER_ROUTE
TARGETED_TESTS
FINAL_TREE_QUALITY_GATE
EXACT_SHA_CI
RELEASE_PUBLICATION
```

Do not promote an earlier gate or canary to final evidence after later code, state-schema, rule, or contract changes.
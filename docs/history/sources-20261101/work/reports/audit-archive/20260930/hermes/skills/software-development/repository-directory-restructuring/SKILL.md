---
name: repository-directory-restructuring
description: Use when restructuring repo dirs at scale with CI fixes.
---

# Repository Directory Restructuring

## When to Use

- Moving from a flat/mixed tree to a layered architecture (packages/, integrations/, services/)
- Splitting monolithic directories into semantic groups
- Migrating third-party code to vendor/research/candidates
- Any restructuring that touches 50+ files

## Pre-Flight Checklist

1. **Create migration branch**: `git checkout -b migration/<name>`
2. **Freeze asset inventory**: `git ls-files` → classify every file by source/license/disposition
3. **Define path mapping**: old_path → new_path for every directory being moved
4. **Create .project governance**: manifest.yaml, gates.yaml, path-risk.yaml
5. **Set up .project-local/**: for runtime data (gitignored)

## Execution Order (Critical)

### Phase 1: Move directories with git mv

```bash
# Always use git mv, not plain mv — preserves history
git mv old/path new/path

# If destination exists (from mkdir -p), remove it first:
rm -rf new/path && git mv old/path new/path
```

**Pitfall**: `git mv` fails with "destination already exists" if you created the target directory with `mkdir -p`. Remove the empty target first.

### Phase 2: Update all path references

Use execute_code to batch-update references across all tracked files:

```python
path_map = {
    "old/path/": "new/path/",
    # ... all mappings
}
for f in tracked_files:
    content = read(f)
    for old, new in path_map.items():
        content = content.replace(old, new)
    if changed: write(f, content)
```

**Pitfall**: String replace can match inside string literals, JSON values, and comments. This is usually fine for path references but verify critical files manually.

### Phase 3: Fix Python import paths

When moving Python packages, tests and scripts need updated `sys.path.insert`:

```python
# For files that define REPO_ROOT or PROJECT_ROOT:
sys.path.insert(0, str(REPO_ROOT / "packages" / "capabilities"))

# For files that only define DESIGN_LAB:
sys.path.insert(0, str(DESIGN_LAB.parent / "packages" / "capabilities"))
```

**Critical pitfalls**:
- **Don't add sys.path.insert to library modules** (only scripts/tests). Library modules are imported, not run directly.
- **Watch for duplicate lines** — running the fix script twice inserts duplicates.
- **Check variable names** — some files use `REPO_ROOT`, others `PROJECT_ROOT`, others `DESIGN_LAB`. Match the existing variable.
- **Fix parents[N] depth** — if a file moved from depth 2 to depth 3, `Path(__file__).resolve().parents[2]` needs to become `parents[3]`.
- **from __future__ imports must be first** — don't insert sys.path.insert before them.

### Phase 4: Update CI workflows

```yaml
# Update working-directory references
working-directory: new/path  # was old/path

# Update path triggers
paths:
  - 'new/path/**'

# Update requirements.txt references
-r new/path/requirements-core.in  # was -r old/path/requirements-core.in

# Update change detection patterns
grep -qE '^(new/path1|new/path2)/' 
```

### Phase 5: Update sidecar files

Binary assets with `.license` sidecars need the `file` field updated:

```python
for lf in glob("*.license"):
    data = json.load(lf)
    if "file" in data:
        data["file"] = data["file"].replace("old/path/", "new/path/")
        json.dump(lf, data)
```

### Phase 6: Clean up old directories

```bash
# Remove tracked old directories
git rm -r old/path/

# Remove untracked remnants
rm -rf old/path/

# Verify no tracked files remain
git ls-files old/path/
```

### Phase 7: Verify and commit

```bash
# Run full verifier chain
python design-lab/scripts/verify_design_lab.py

# Check for remaining old path references
grep -rn "old/path" --include="*.py" --include="*.json" --include="*.md"

# Commit with task pack references
git commit -m "feat(TASK-ID): description"
```

### Phase 8: Converge the post-migration CI gate suite (anti whack-a-mole)

After a scale migration the CI gate suite fails dozens of checks that local runs never exercise in the same shape. Churning one fix-commit per failure is the "loop" the user reads as spinning (they will say 循环幻觉/老出模型错误) — stop it with this discipline:

1. **Enumerate every failing step first, once.** Pull the complete job log and list ALL FAILED/ERROR/exit-N steps before touching code:
   ```bash
   gh api repos/OWNER/REPO/actions/jobs/$JID/logs --allow-escape-sequences \
     | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g'   # strip ANSI, then grep FAILED/ERROR/exit N
   ```
   Check which workflows ran on the same commit (`gh run list --workflow NAME`): push + PR sync can double-trigger, and aggregate/integration jobs race jobs still `in_progress` — a "required job missing/failed" verdict can be a timing artifact, not a code failure.
2. **Ask "was this green at baseline?" before fixing a failing suite.** A gate whose fixture files were never tracked (tests assert a root `setup.sh` git never contained, or assert old module-README content after the root README was rewritten repo-wide) was red before the migration too — the migration only surfaced it. Classify each failure: (a) stale path/`parents[N]`/sys.path → real, fix; (b) **test-obligation drift** — the assertion target is no longer the right object (re-point to the module-scoped doc/archive, or turn a full-tree enumeration assertion into a link-integrity assertion); (c) never-green-at-baseline → report to the user, don't silently "fix".
3. **CI runs suites local pytest never does.** Workflow YAML often appends direct runs after the gates: `python tests/<area>/test_X.py`. Direct mode bypasses conftest.py and the gate runner's injected PYTHONPATH, so every such file needs its own self-locating header:
   ```python
   ROOT = Path(__file__).resolve().parents[2]   # repo root, not tests/
   sys.path.insert(0, str(ROOT / "packages/.../scripts"))
   sys.path.insert(0, str(ROOT / "services/..."))   # per imported module dir
   ```
   Grep the workflow file for the full direct-run list and execute each command locally exactly as CI does before pushing.
4. **unittest discovery ≠ pytest.** `python -m unittest -v t1 t2 ...` resolves imports only through the PYTHONPATH the runner injects. Collect the real module-root list once (services/*, packages/*/scripts, integrations/*/executors/*, tests/*) and reuse it.
5. **2-round stop-loss.** If the same gate is not green after two local fix rounds, stop and report status instead of pushing another commit. Batch fix commits by failure class and verify each locally with the CI's own command before pushing.

Full per-class failure catalogue and recipes: `references/ci-gate-convergence-playbook.md`.

### Phase 9: Evict third-party full source from Git (post-migration finalization)

When the target state says "no third-party full copies in Git" (CONDITIONAL_POC → index only, source in ignored cache):

1. **Classify every candidate tree before moving**: third-party = has SOURCE.md/LICENSE at its root; project-own docs mixed into the same folder are NOT third-party — separate them first (`git mv` own docs to a design-lab/research/... home, move only the vendored roots).
2. **Copy to the ignored cache BEFORE git rm** (fidelity backup): `shutil.copytree(src, .project-local/cache/vendor/<key>)`, record a manifest (src → cache key, file count). Deletions are only safe after the copy is verified. 37 roots / 1900+ files was fine in one pass.
3. **Remove tracked trees, then STAGE the deletions** (`git add -A <tree>`). Unstaged deletions leave the index referencing missing files → any verifier that stats every tracked path (asset-governance) fails with "cannot stat tracked file" until the deletions are staged and committed.
4. **Keep an index in the emptied dir** (README with per-root URL/license/disposition/cache key) so the location still documents itself; append entries to vendor/sources.lock.json.
5. **Fix every declared-path manifest**: product-manifest.json capability-family `paths` are *existence-asserted* — a family pointing at `research/candidates/visual-quality/` fails `path exists` the moment the docs move out. Re-point to the new home.
6. **Update the anti-slop/CI skip-prefix lists in BOTH places** (workflow yaml AND verify_design_lab.py) to drop prefixes of deleted dirs — keep them in sync.
7. **Watch CRLF**: the patch tool writes LF; on a CRLF-normalized repo, re-run a CRLF normalization pass (python `replace(b'\n', b'\r\n')`) on edited .json/.md before committing or the diff churns whole files.

Full worked recipe (roots, gate interactions, count semantics): `references/third-party-eviction-finalization.md`.

## Generator/Verifier Asymmetry (silent stale artifact trap)

A post-migration repo can keep a gate green while its *generator* is broken for weeks: the generate script scans deleted dirs and crashes, but the committed generated artifact (e.g. asset-counts.json) still satisfies the verifier because the verifier only compares a subset of fields. You only notice when you run the generator.

- **After any migration, run the generators, not just the verifiers.** A verifier that PASSES proves nothing about whether regeneration reproduces the committed artifact.
- When a generator is fixed and real counts surface, **stale tests that asserted the old fabricated number now fail — decide the counting semantics**, don't blindly update the number or revert the fix. Example: `design_systems` count. Directory scan said 4 (a project-only system sat next to 3 managed ones); installer/authoritative sources said 3. Correct semantics = count only managed systems (manifest carries a `source: DESIGN-LAB/...` lineage marker), matching the installer's source list and the test's `== 3`.
- Migrations that move catalog dirs need the SAME path-remap logic in both generate and verify halves (`plugins/bundles/atoms/scenarios` → packages/capabilities/, `hosts/*` → integrations/, else design-lab/).



| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` after move | sys.path not updated | Add packages/capabilities to sys.path |
| `NameError: REPO_ROOT not defined` | Wrong variable name in sys.path.insert | Match existing variable |
| `SyntaxError: from __future__` | sys.path.insert placed before future import | Remove from library modules |
| `FileNotFoundError: schema.json` | parents[N] depth wrong after move | Increment N |
| `sidecar file mismatch` | .license file field has old path | Update "file" field |
| CI `No such file or directory` | workflow working-directory still old | Update canonical-verify.yml |
| CI `requirements file not found` | requirements.txt references old path | Update -r path |
| `git mv` fails | Destination directory exists | `rm -rf dest && git mv src dest` |
| Verifier: "cannot stat tracked file" | Bulk git rm left deletions unstaged; index references missing files | `git add -A <tree>` to stage deletions, then commit |
| Verifier: "FAIL path exists: <old candidate dir>" | Manifest capability-family `paths` still points at emptied/moved dir | Re-point to new home in product-manifest.json |
| Gate green but generator crashes | Verify half migrated, generate half still scans deleted dirs; committed stale artifact masks it | Run the generator; port the same path-remap to both halves |
| Test asserts old count after generator fix | Real count was masked by stale artifact; assertion codified the stale number | Decide counting semantics (managed vs all) from authoritative sources, then update test+generator together |

## Verification Checklist

- [ ] `git ls-files | wc -l` — file count changed as expected
- [ ] `python design-lab/scripts/verify_design_lab.py` — all verifiers pass
- [ ] `grep -rn "old/path" --include="*.py"` — zero matches
- [ ] `git status --short` — clean or only expected changes
- [ ] CI workflow paths updated in `.github/workflows/`
- [ ] requirements.txt updated if it referenced moved directories
- [ ] Sidecar .license files updated for moved binaries
- [ ] Third-party trees copied to ignored cache BEFORE deletion; deletions staged (`git add -A`) and committed before asset-governance-style verifiers
- [ ] Generators re-run (not just verifiers) — committed artifacts match regeneration
- [ ] Product-manifest capability-family paths point at existing dirs (existence-asserted)
- [ ] CI workflow AND local verify_design_lab skip-prefix lists in sync after dir deletions
- [ ] CRLF-normalized files re-normalized after patch edits (1-line diffs, not whole-file churn)

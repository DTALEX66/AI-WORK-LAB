---
name: repository-restructuring
description: Use when moving repo directories or fixing migration paths.
---

# Repository Restructuring

## When to Use
- Moving large directory trees (capabilities, adapters, knowledge) to new locations
- Restructuring a monorepo into packages/services/integrations layers
- Migrating third-party code between quarantine, research, and production directories

## Workflow

### Phase 1: Freeze & Inventory
1. Create migration branch: `git checkout -b migration/<name>`
2. Create `.project-local/` isolation directory
3. Scan all tracked files: `git ls-files | wc -l`
4. Classify each directory: ABSORB_MINIMAL / CONDITIONAL_POC / LOCK_REFERENCE / REJECT_REMOVE
5. Record inventory to `reports/migration/`

### Phase 2: Move & Absorb
1. Use `git mv` for tracked files (preserves history)
2. For `git mv` failures when destination exists: `rm -rf <dest>` first, then retry
3. For untracked files: `rm -rf` directly
4. Commit each logical batch separately

### Phase 3: Fix Python Import Paths (CRITICAL)
After moving Python modules, ALL import references must be updated:

**Scripts/tests that import moved modules:**
```python
# Before (old location):
sys.path.insert(0, str(DESIGN_LAB))  # design-lab/reconstruction was here

# After (new location — add new path):
sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(REPO_ROOT / "packages" / "capabilities"))
```

**Library modules that use `Path(__file__).resolve().parents[N]`:**
When a file moves from `design-lab/reconstruction/` (depth 2) to `packages/capabilities/reconstruction/` (depth 3), update:
```python
# Before:
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # was 2 levels deep

# After:
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # now 3 levels deep
```

**Pitfalls:**
- Do NOT add `sys.path.insert` to library modules (only scripts/tests)
- Do NOT create duplicate `sys.path.insert` lines
- Check which root variable is defined (REPO_ROOT vs PROJECT_ROOT vs DESIGN_LAB) before referencing
- `from __future__ import annotations` MUST be at file start — never insert lines before it

### Phase 4: Fix Sidecar Files
Binary assets with `.license` sidecars need path updates:
```json
{
  "file": "design-lab/knowledge/visual-quality/...",  // OLD path
  "sha256": "...",
  "license": "MIT"
}
```
Update `file` field to match new location. Use batch script:
```python
path_map = {
    'design-lab/knowledge/': 'research/candidates/',
    'design-lab/intelligence/': 'research/candidates/',
    'minigame-runtime/': 'fixtures/domains/game-visual/',
    'design-lab/adapters/creative-tools/': 'integrations/generators/',
}
```

### Phase 5: Update All References
Bulk find-and-replace across all tracked files:
```python
path_map = {
    "design-lab/reconstruction": "packages/capabilities/reconstruction",
    "design-lab/atoms": "packages/capabilities/atoms",
    # ... etc
}
for f in files:
    content = open(f).read()
    for old, new in path_map.items():
        content = content.replace(old, new)
```

### Phase 6: Test Matrix
Run full verifier chain. Common post-migration failures:
- `ModuleNotFoundError: No module named 'reconstruction'` → missing sys.path entry
- `NameError: name 'REPO_ROOT' is not defined` → wrong root variable used
- `SyntaxError: from __future__ imports must occur at the beginning` → inserted line before future import
- `FileNotFoundError: ...schema.json` → parents[N] depth wrong
- Sidecar mismatch → .license file path not updated

### Phase 7: Clean Up
1. Delete old directories: `git rm -r <old>` for tracked, `rm -rf` for untracked
2. Clean `.hermes/` runtime data (old worktrees, caches, test artifacts)
3. Update `.gitignore` if needed
4. Final commit and PR

### Phase 8: Post-Migration Consistency (generators, artifacts, index)

Directory moves leave generators, committed generated artifacts, and index files pointing at the old world. Close these drift classes before merging:

**Generator drift masked by stale output.** After moving/removing directories, run every repo generator. A generator crashing on a deleted directory means its committed output predates the migration — fix the generator's scan roots to the new layout, regenerate, and commit the output. Do not trust a green gate over an old artifact: verifiers may compare only the fields that happen to match.

**Test + generated-file co-lying.** A test asserting a count read from a generated index passes on stale data when test, artifact, and real directory disagree (test expects 3, artifact says 3, directory has 4). Regenerate the artifact first, then reconcile the test with the authoritative managed list — never with the stale artifact.

**Managed-count semantics.** When a count field mirrors an installer's managed resource list, derive it from that list or a manifest lineage marker, not a raw directory glob — raw scans pick up local project-only assets that were never part of the managed surface.

**Mass-deletion staging.** Mass `git rm` can leave deletions visible in the index but not staged; verifiers that stat tracked files then fail with `cannot stat tracked file <old-path>`. After any mass removal, confirm `git status --short` shows deletions in the FIRST (staged) column — `git add -A` if not — before running fs-stat-based gates.

**Manifest path existence.** Product manifests declaring capability-family paths are existence-checked by verifiers. When a family's source directory moves, update the manifest declaration in the same change, or the gate fails with `path exists: <old-path>`.

## Windows-Specific Notes
- MSI installers need admin rights → use portable .zip versions instead
- NSIS installers (.exe) need `cmd.exe /c "start /wait installer.exe /S"` from bash
- `winget` may not be available → use direct download + manual install
- Use `curl -x http://127.0.0.1:7890` for HuggingFace/GitHub downloads behind proxy

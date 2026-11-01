# Release gate evidence matrix (three-dimension pattern)

A reusable template for verifying a release artifact's build, installer lifecycle, and public distribution readiness. Separates three evidence dimensions that are frequently conflated.

## Matrix format

| Dimension | Evidence | Gap | Gate | Honest manifest claim |
|---|---|---|---|---|
| **Build (wheel)** | ✅ Verified — wheel built, checksummed | N/A | `python -m build --wheel` | `version: 0.4.0` |
| **Build (desktop/NSIS)** | ⚠️ Partial — CI builds on `main` but not current branch | Current-branch desktop build not run (45-min Rust/Tauri toolchain) | CI `desktop-shell` job | `build_status: partial` |
| **Checksum generation** | ✅ Script creates SHA-256 manifest | N/A | `scripts/release_checksum.py` | Checksum file separate from manifest |
| **Provenance injection** | ✅ Script injects commit/tree/CI-run | N/A | `scripts/release_inject_identity.py` | Source manifest stays `unavailable` until public |
| **SBOM** | ❌ Not implemented | No CycloneDX tooling or workflow | `cyclonedx-bom` generation | Not in manifest |
| **Tag-only release workflow** | ❌ Not implemented | No `.github/workflows/release.yml` with tag trigger | Protected CI with `contents: write` | `public_installer: not_implemented` |
| **Release manifest honesty** | ✅ Verified | N/A | `load_release_manifest()` validates schema | `source.commit: unavailable`, `status: unreleased` |
| **Installer lifecycle** | ⚠️ Partial — CI verifies NSIS install/start/shutdown/uninstall on `main` | Current tree not exercised | `verify_nsis_install.ps1` | N/A until public |
| **Public distribution** | ❌ Not implemented | No release upload, signing, or publication | Tag + approval + upload + readback | `public: false` |

## Acceptance criteria per dimension

### Build evidence

Required: the artifact is created from the current tree and its identity (name, version, byte hash) is recorded.

- ✅ **Verified**: wheel built from current tree, SHA-256 recorded, identity manifest written.
- ⚠️ **Partial**: artifact was built from a different tree (e.g., CI on `main`, not current branch), or the build takes 45+ minutes and was skipped with reason documented.
- ❌ **Missing**: build script does not exist, build fails, or artifact is not tested.

### Installer lifecycle evidence

Required: the installer is actually installed on the target OS, the application starts and responds to health checks, and shutdown + uninstall complete cleanly.

- ✅ **Verified**: installer exercised on real Windows, health endpoint returns 200, graceful shutdown succeeds, uninstall removes all files.
- ⚠️ **Partial**: CI verifies lifecycle but not on the current tree (different SHA/branch), or the installer was built but never installed and tested.
- ❌ **Missing**: no installer lifecycle verification exists at all.

### Public distribution evidence

Required: a tag-only release workflow injects exact source identity, produces checksum/signature/SBOM, uploads artifacts, creates a GitHub Release (or equivalent), and reads the published assets back for byte-level verification.

- ✅ **Verified**: release published, source identity injected, assets verified by checksum, public readback confirms exact artifacts.
- ❌ **Not implemented**: no release workflow exists, no upload/publication step, or `contents: read` permission prevents publication. The release manifest should truthfully report `status: unreleased` and `public: false`.

## Classifying when a dimension is impractical

Not all dimensions can be exercised on every tree. Common reasons:

| Reason | Classification | Reporting |
|---|---|---|
| Desktop build takes >30 min with heavy toolchain | ⚠️ Partial | "Not run on current tree — CI runs on main" |
| No Windows CI runner available | ⚠️ Partial or ❌ Gap | "No Windows CI job configured" |
| User has not authorized public release | ❌ Not implemented | Correctly reported in manifest |
| Tool/binary not installed locally | ⚠️ Partial | "Requires CI — local toolchain unavailable" |

**Never** convert a partial or blocked dimension into a pass. The release manifest's capability values (`not_implemented`, `dependency_required`, `available`) are the source of truth — they should not be mutated to fabricate progress. Report the honest state and proceed to the next dependency-ready dimension.

## Relationship to the sleep-mode queue

When a release gate is the final task in a sleep-mode queue (as with N-001), the queue transitions to `completed` even though the public-distribution dimension is `not_implemented`. This is correct: the task was to *implement and verify* the release gate infrastructure, not to *execute* a public release. A subsequent task or release cycle handles the actual publication when the user authorizes it.

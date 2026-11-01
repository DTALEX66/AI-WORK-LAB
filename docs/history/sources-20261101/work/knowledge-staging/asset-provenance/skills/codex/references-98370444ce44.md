---
name: references
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-observer-delivery/references/rust-tauri-toolchain-floor.md
---

# Rust/Tauri toolchain version floor pitfall (2026-08-11)

## Symptom
`cargo build` on a Tauri 2.x project failed with:
```
error: failed to parse manifest at ...\idna_adapter-1.2.2\Cargo.toml
feature `edition2024` is required ... not stabilized in this version of Cargo (1.77.2)
```
Later (after upgrading to 1.85) the resolver printed explicit floors:
```
icu_properties_data@2.2.0 requires rustc 1.86
plist@1.10.0 requires rustc 1.88.0
time@0.3.55 requires rustc 1.88.0
serde_with@3.22.0 requires rustc 1.88
```

## Root cause
A documented minimum rust-version (e.g. contract says rust 1.77.2) is a FLOOR, not a
guarantee. Current crates.io resolution of a tauri 2.11.x dependency chain pulls crates
that use `edition2024` (needs cargo >= 1.85) and some that declare `rust-version 1.88`
(plist 1.10.0, time 0.3.55, serde_with 3.22.0). cargo 1.77.2 happily RESOLVES those
versions and only fails at compile/parse time. Deleting Cargo.lock does not help — the
resolver re-picks the same editions. Precise-downgrading individual crates deadlocks
against the dependency constraints (e.g. tauri 2.11.3 -> plist ^1 -> time >= 0.3.5x).

## Fix (working path)
Install a newer toolchain alongside the old one — rustup keeps them side by side, fully
reversible:
```bash
rustup toolchain install 1.88.0 --profile minimal
rustup default 1.88.0
```
Then re-run `cargo build` / `cargo test` with the same Cargo.toml (tauri version stays
pinned). No Cargo.lock surgery needed once the toolchain is high enough.

## Portable install (no PATH modification, user-chosen dir)
```bash
RUSTUP_HOME="D:\\...\\.rustup" CARGO_HOME="D:\\...\\.cargo" \
  ./rustup-init.exe -y --no-modify-path --default-toolchain 1.77.2 --profile minimal
export RUSTUP_HOME=... CARGO_HOME=... PATH="$CARGO_HOME/bin:$PATH"   # per-shell
```
MSVC Build Tools (cl.exe) can be installed to a non-default path:
```
vs_buildtools.exe --quiet --wait --norestart --nocache \
  --installPath "D:\...\BuildTools" --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended
```

## Verification
- `rustc --version` / `cargo --version` after `rustup default`
- `rustup target list --installed` shows x86_64-pc-windows-msvc
- `cargo test` in src-tauri compiles and runs the unit test

## Notes
- tauri bundle patches app.exe during `cargo tauri build` (embeds installer type info) —
  the EXE SHA changes between `cargo build` and `cargo tauri build`; record SHA from the
  BUNDLED artifact, not the raw build.
- `cargo tauri build` with `"targets": "all"` downloads WiX (for MSI) and NSIS at build
  time from GitHub — needs network; produces .msi + -setup.exe under bundle/.
- NSIS `/S /D=<dir>` custom dir did NOT take effect for a tauri-generated installer;
  the per-user MSI (`msiexec /i ... /qn`, installs to %LOCALAPPDATA%\<ProductName>) is the
  reliable scripted install path. Uninstall via the generated uninstall.exe /S leaves
  system clean.

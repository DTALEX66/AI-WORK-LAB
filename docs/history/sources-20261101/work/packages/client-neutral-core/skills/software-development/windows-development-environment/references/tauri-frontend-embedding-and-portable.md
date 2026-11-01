# Tauri Frontend Embedding & Portable Flag Detection (validated 2026-08-30)

## Critical: `cargo build` does NOT embed frontend

Plain `cargo build --release --bin archeaxis-desktop-shell` compiles Rust code but does NOT embed the frontend files from `frontendDist`. The exe will show `about:blank` in the WebView.

**Root cause**: `tauri_build::build()` in `build.rs` should embed the frontend, but cargo's build script caching can skip re-running it when frontend files change. Even after `cargo clean`, the embedding may not work correctly with plain `cargo build`.

**Correct approach**: Use `cargo tauri build --no-bundle` which explicitly runs the Tauri bundler and embeds `frontendDist`.

**Problem**: `cargo tauri build` requires `dlltool.exe` (GNU binutils) which is NOT available on MSVC-only toolchains. The `parking_lot_core` crate needs it.

**Workarounds**:
1. Install MinGW/MSYS2 `binutils` and add to PATH
2. Use CI (GitHub Actions) which has full toolchain
3. Use `scoop install mingw` to get `dlltool.exe`

## Tauri `frontendDist` path resolution

`frontendDist: "../bootstrap"` in `tauri.conf.json` is relative to `src-tauri/`. So:
- `desktop/src-tauri/tauri.conf.json` → `frontendDist: "../bootstrap"` → `desktop/bootstrap/`
- The frontend must be in `desktop/bootstrap/` at build time
- `frontend/dist/` is NOT the same as `desktop/bootstrap/`

**Build sequence**:
1. Build frontend: `npm --prefix frontend run build`
2. Copy to bootstrap: `cp frontend/dist/* desktop/bootstrap/`
3. Build Tauri: `cargo tauri build --no-bundle`

## Tauri portable.flag detection (Rust code fix)

The Tauri exe's Rust code only checks environment variables (`ARCHEAXIS_PORTABLE_ROOT`, `COGNITIVE_PORTABLE_ROOT`) for portable mode. It does NOT check for `portable.flag` file by default.

**Fix**: Add `portable.flag` detection to `lib.rs`:
```rust
let portable_root = std::env::var_os("ARCHEAXIS_PORTABLE_ROOT")
    .or_else(|| std::env::var_os("COGNITIVE_PORTABLE_ROOT"))
    .map(PathBuf::from)
    .or_else(|| {
        // Check for portable.flag beside the executable
        let exe = std::env::current_exe().ok()?;
        let distribution_root = exe.parent()?;
        distribution_root
            .join("portable.flag")
            .is_file()
            .then(|| distribution_root.join("data"))
    });
```

Without this fix, the green version's exe always uses `AppData/Local` as data root, even with `portable.flag` present.

## Version release workflow lessons

1. **Tags are protected** on GitHub and cannot be force-updated
2. **Always run ALL verification scripts locally** before creating an immutable tag
3. **PowerShell 7 exception types** differ from PowerShell 5.1 (see `crlf-hash-and-powershell7-catch.md`)
4. **Version bump required** for each release attempt — cannot reuse version numbers
5. **`verify_zip_distributions.ps1`** and **`verify_nsis_install.ps1`** must both handle 410 responses

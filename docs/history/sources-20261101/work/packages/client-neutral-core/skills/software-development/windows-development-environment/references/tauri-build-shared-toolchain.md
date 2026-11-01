# Tauri 桌面构建配方：Windows 共享工具链

> Current after the post-ENV-103 toolchain move. Treat repository `EXTERNAL_DEPENDENCIES.md` and live file checks as authority; dated absolute paths in old logs are not authority.

## Preconditions

1. Read the Tauri project's `Cargo.toml` and `tauri.conf.json`.
2. Verify the intended packaging command. For an embedded production frontend use:

```text
cargo tauri build --no-bundle
```

Plain `cargo build --release` is only a Rust release build and may retain the development URL instead of embedding `frontendDist`.
3. Keep `CARGO_TARGET_DIR`, logs, PID files, screenshots, and other generated evidence inside the active project's ignored `.hermes/task-runtime/` or declared project target directory.
4. Resolve tool locations before building. Do not declare the desktop toolchain missing merely because `cargo` is absent from the Git-Bash/wrapper PATH.

## Current shared-toolchain layout

The validated post-move layout is:

| Component | Current location |
|---|---|
| Rust root | `D:\All projects\OS External Configuration\toolchains\rust` |
| Rust/Cargo toolchain bin | `...\rustup\toolchains\1.88.0-x86_64-pc-windows-msvc\bin` |
| Cargo home / cargo-tauri lookup | `...\rust\cargo` |
| MSVC vcvars | `D:\All projects\OS External Configuration\10-toolchains\msvc\VC\Auxiliary\Build\vcvars64.bat` |

The retired path `...\toolchains\vs-build-tools\...` must not be used as current authority. If the repository's external-dependency manifest names a different version/location, follow that manifest and verify the exact files before executing.

## Reliable wrapper-safe build shape

Git-Bash can resolve GNU `/usr/bin/link.exe` ahead of Microsoft's linker. Route the build through a project-local `.bat` under `.hermes/task-runtime/` so `vcvars64.bat` establishes the MSVC environment first.

```bat
@echo off
setlocal
call "D:\All projects\OS External Configuration\10-toolchains\msvc\VC\Auxiliary\Build\vcvars64.bat"
set "RUST_BASE=D:\All projects\OS External Configuration\toolchains\rust"
set "RUST_BIN=%RUST_BASE%\rustup\toolchains\1.88.0-x86_64-pc-windows-msvc\bin"
set "RUSTUP_HOME=%RUST_BASE%\rustup"
set "CARGO_HOME=%RUST_BASE%\cargo"
set "PATH=%RUST_BIN%;%CARGO_HOME%\bin;%PATH%"
cd /d "<project>\src-tauri\.."
"%RUST_BIN%\cargo.exe" tauri build --no-bundle
exit /b %ERRORLEVEL%
```

Launch the `.bat` from a small project-local Python script when the Hermes project-data wrapper requires a single child command:

```python
from pathlib import Path
import subprocess

script = Path(__file__).with_name("build-tauri.bat")
result = subprocess.run(
    [str(script)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
print(result.stdout.decode("utf-8", errors="replace"), end="")
raise SystemExit(result.returncode)
```

Why capture bytes: mixed CMD/MSVC output may contain a Windows code page. Passing it unmediated to a UTF-8-only wrapper can kill the reader thread. `errors="replace"` preserves the useful Cargo diagnostics without making decoding the build result.

## Network policy

Do not hard-code a VPN/localhost proxy into the build recipe. Use cached/offline dependencies when complete. If dependencies are missing, follow the user's current network policy and an explicitly approved registry/mirror; do not silently route large downloads through a VPN. A network/cache miss is an environment state, not a durable claim that Tauri cannot build.

## Verification layers

A successful compile is only one layer:

1. **Build:** command exits 0 and log contains the optimized release finish marker.
2. **Artifact:** `app.exe` has a new mtime/size/hash from this build; never reuse the previous executable as evidence.
3. **Process:** launch the exact artifact and confirm one intended process/window chain.
4. **WebView:** read live DOM/CSS through CDP or the supported computer-use/browser path. `PrintWindow` may capture a black WebView2 surface because of GPU rendering; do not rely on it as the only visual proof.
5. **Backend:** verify the exact loopback Sidecar endpoint and distinguish external Sidecar operation from a self-contained desktop bundle.
6. **Lifecycle:** close/restart and read back state if desktop lifecycle is in scope.
7. **CI/release:** local build/runtime evidence does not prove exact-SHA CI or public distribution.

## Failure triage

| Symptom | Interpretation | Next action |
|---|---|---|
| `cargo` or `cargo.exe` not found under wrapper | PATH resolution issue | resolve the manifest-declared full executable path |
| `link: extra operand ...` | GNU coreutils `link`, not MSVC linker | use the `.bat`/vcvars path; do not keep retrying Cargo directly from Git-Bash |
| vcvars path missing | dependency-path drift or missing toolchain | re-read the external dependency manifest and verify current post-move path before reporting a blocker |
| output reader `UnicodeDecodeError` | code-page mismatch | capture bytes and decode with `errors="replace"` |
| build exits 0 but app loads dev URL/blank page | wrong build entry | use `cargo tauri build --no-bundle` and inspect embedded `frontendDist` |
| stale old `app.exe` is still running | runtime evidence contamination | terminate only the exact stale artifact and relaunch the new build |

Never turn a failed path probe into the persistent claim “MSVC/Tauri is unavailable.” Report the exact attempted layer, then discover the current manifest-owned toolchain path.

---
name: windows-portable-toolchain-boundaries
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/windows-portable-toolchain-boundaries/SKILL.md
---

---
name: windows-portable-toolchain-boundaries
description: "Configure shared Windows portable toolchains without leaking project runtime state, credentials, or package-manager caches across roots."
version: 1.0.0
---

# Windows Portable Toolchain Boundaries

## Use when

Use when a user authorizes a shared external Windows toolchain/configuration root while an active repository must retain isolated runtime state and auditable project boundaries.

## Core boundary

1. Put reusable executable toolchains, browser binaries, compiler homes, and package-manager caches under the explicitly authorized external toolchain root.
2. Put application databases, logs, generated smoke output, temporary server state, and agent task artifacts under the active repository's ignored `.hermes/task-runtime/<task>/` directory by default.
3. Never put API keys, JWT fallback files, credentials, application databases, or runtime logs into a tracked configuration/toolchain repository.
4. Do not introduce symlinks or external application-YAML loading unless the app already supports that exact configuration mechanism and the user approved it.

## Shared multi-project toolchain library

When the external toolchain root is shared across multiple projects (not one
project's private dependency root):

1. Declare it shared in the root README and the dependency-authority doc —
   replace "本项目专属 / 服务本开发机" wording with "跨项目共用".
2. Maintain a project→tool index (`00-registry/project-tool-index.yaml`) listing,
   per project, each consumed tool with `path / version / purpose / reference`.
   New projects append entries instead of guessing ownership. This is what keeps
   a shared root from becoming an untraceable grab-bag.
3. On any duplicate tool across projects, keep the newest stable version and
   point the older consumer at it (user rule: 重复以新版本稳定版为准).
4. Produced content stays in the project: runtime artifacts, caches, logs, and
   generated output live under the project's `.hermes/task-runtime/`, never in
   the shared root. The shared root holds tool binaries + index + manifests only.
   Migrating model caches and activating per-tool env vars (HF_HOME, MODELSCOPE_CACHE,
   TESSDATA_PREFIX, PLAYWRIGHT_BROWSERS_PATH) into the shared root: see
   [`references/shared-toolchain-migration.md`](references/shared-toolchain-migration.md).
5. Assets a project stores in a shared library (model weights, design-source
   material) need an in-repo ownership index — not just a tool index — so the
   shared root stays attributable. A git-tracked `external-assets-index.json`
   (+ JSON Schema) lists each asset with `owned_by` / `shared_root` /
   `relative_path` / `size_bytes`; a verifier in the canonical gate checks ONLY
   environment-independent facts (schema validity + every asset references a
   declared `shared_root`). Do NOT gate on path existence — the shared root is
   outside the repo and differs per machine, so CI would false-fail. Full
   pattern + verifier/schema gotchas:
   [`references/shared-asset-indexing.md`](references/shared-asset-indexing.md).

## Portable Node/npm checklist

A portable Node path alone is insufficient. Set and verify both:

```text
NPM_CONFIG_CACHE=<toolchain-root>\scoop\persist\nodejs-lts\cache
NPM_CONFIG_PREFIX=<toolchain-root>\scoop\persist\nodejs-lts\bin
```

Apply them consistently in Bash activation, CMD activation, and the Windows User-environment setup script. Then source/activate the toolchain and verify:

```bash
npm config get cache
npm config get prefix
```

Both paths must be within the approved external toolchain root. This prevents mutable npm state from silently returning to an obsolete per-user Scoop root.

## Isolated local UI/runtime smoke

1. Set `COGNITIVE_DATA_DIR` to `<repo>/.hermes/task-runtime/<task>`.
2. Create the runtime directory only through the app's supported configuration resolution.
3. Apply the product's real migration operator or runtime migration command. Do not treat a successful Python module import as proof that migrations executed.
4. Run the application's own schema validation before launching a server.
5. Bind the smoke server only to `127.0.0.1`.
6. Probe a real GET route before browser automation; distinguish a route-level `405` for HEAD from an unavailable server.
7. Keep smoke artifacts in the ignored project runtime root and do not commit them.

## Verification and delivery

For Windows Tauri production builds without a usable Visual Studio/MSVC installation, load [`references/tauri-msvc-portable-build.md`](references/tauri-msvc-portable-build.md). It covers project-local xwin SDK/CRT staging, `rust-lld`, the separate C++/resource-tool boundaries, temporary Cargo patch cleanup, artifact hashing, WebView2 cache isolation, sidecar readiness, exact-artifact CDP, and final process cleanup.

- Read back Windows User-scope variables after configuring them; do not rely solely on script success text.
- Test the activation script and package-manager effective configuration in a fresh shell context.
- For browser automation failures involving package-manager state, inspect effective cache/prefix first and repair the toolchain setup rather than changing product code.
- Keep external-toolchain repository commits separate from application repository commits and push each only after its own focused verification.

## Pitfalls

- A config repository is not automatically an application runtime root.
- Moving only a primary SQLite path can leave backups, logs, reports, locks, or fallback secrets elsewhere; use the application-wide data-root setting only when runtime relocation is explicitly intended.
- A success exit code from a no-op module invocation is not migration evidence; require schema validation/readback.

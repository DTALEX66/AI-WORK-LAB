# Stale Bundle Readiness Reference

## Reproduction shape

1. Start a fresh project-local migration/data root.
2. Start the exact bundled backend used by the current desktop executable.
3. Discover the owned loopback port from the child log/readiness signal.
4. Capture a secret-safe response:

```bash
curl --noproxy '*' --http1.1 -i --max-time 5 \
  -H 'X-ArcheAxis-Launch-Token: [TEST-ONLY-TOKEN]' \
  'http://127.0.0.1:<owned-port>/workspace/api/_desktop/ready'
```

Record only status, headers, byte count/framing, and the readiness JSON shape. Never record the real token.

## Provenance comparison

Compare these independently:

- checkout route identity;
- staged wheel/package identity;
- `target/release/runtime/python/Lib/site-packages/app/...` identity;
- identity parsed by the Rust probe;
- WebView title/product identity.

A stale package can return `200` with a prior product/workspace name. The correct response is to rebuild/stage the current wheel, not to accept both names.

## Current-bundle staging pattern

Use the repository's supported bundle command with destination below the worktree's `.hermes` boundary. Verify imports and module provenance before launch. After the final Cargo/Tauri build, repeat the provenance check because build scripts may recreate `target/release/runtime` and invalidate a manual link or copy.

## Evidence shape

```text
raw_response: 200
transport: <content-length|chunked>
body_shape: {schema_version, product, workspace}
checkout_identity: current
bundle_identity: current
rust_predicate: accepted
native_shell: launched
webview_navigation: accepted
webview_interaction: <pass|partial|not executed>
restart_readback: <pass|partial|not executed>
```

## Boundary rules

Keep all staging, backups, logs, and smoke data under the project ignored runtime directory. Do not access protected data drives, print secrets, modify global Hermes state, or mass-kill unrelated WebView2 processes.

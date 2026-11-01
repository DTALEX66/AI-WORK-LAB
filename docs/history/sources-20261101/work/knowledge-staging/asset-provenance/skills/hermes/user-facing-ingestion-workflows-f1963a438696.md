---
name: user-facing-ingestion-workflows
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/user-facing-ingestion-workflows/SKILL.md
---

---
name: user-facing-ingestion-workflows
description: Build local-first user interfaces for importing real source material (URLs and files) into knowledge or document-processing systems without exposing backend workflow identifiers.
---

# User-facing ingestion workflows

## Use when

Use this skill when a user-facing product screen initiates content processing, knowledge extraction, document conversion, OCR, transcription, or research intake.

## Product boundary

1. Start from the user's source material, never from internal orchestration identifiers.
   - Good controls: paste a URL, select/drop a file, select a folder, choose an import source.
   - Never make normal users provide `command_id`, database IDs, package IDs, artifact IDs, reviewer IDs, or state-machine values.
2. The backend generates correlation IDs, durable receipts, storage names, and transition identifiers internally.
3. Show user-facing progress and results: detected format, conversion engine, extracted text/summary, warnings, next automatic stage, and an optional retry/removal action.
4. Preserve an audit trail internally, but do not present audit mechanics as the primary product workflow.
5. Hiding internal IDs in the DOM is not sufficient if the ordinary browser still receives them in JSON. Add a product DTO boundary: server-side code maps domain IDs to display metadata and, only when selection is required, a purpose-limited opaque `item_ref`. Keep `command_id`, `package_id`, `job_id`, `artifact_id`, `card_id`, and outbox/event IDs out of normal product responses.

## Local-first mode

When the product is explicitly local-first:

1. Do not add API-key/JWT fields or login friction to the local UI unless the user explicitly needs multi-user or remote access.
2. Bind local development/runtime servers to loopback and enforce the boundary for the **entire product router**—page, assets, diagnostics, reads, and writes—not only mutation handlers.
3. A socket peer check alone is not a localhost CSRF boundary. Also require a loopback `Host`, reject `Sec-Fetch-Site: cross-site`, and when `Origin` is present require same-origin. Ignore forwarding headers unless an explicit trusted-proxy policy already validated them.
4. If global API authentication is enabled, compose it deliberately: the local product router may bypass browser credentials only when its mandatory router-level local-only guard still runs. Test that local access works without secrets and remote access remains denied even with valid credentials.
5. Record a stable local principal internally (for example `local-workspace`) for traceability rather than asking the user to identify a reviewer.
6. Remove unnecessary manual approval clicks from the happy path. Keep deterministic records and automatic projections, but make the result of an import visible and reversible.

## Commercial surface vs development internals

Keep naming and disclosure boundaries explicit when an engineering prototype becomes a product screen:

1. Product shell, navigation, settings, installer, and normal task copy use the commercial product/domain names only.
2. Repository names, phase labels, test counts, source paths, migration owners, `TaskPack`, trace IDs, and storage identifiers belong in developer or explicitly expanded audit views—not the default user workflow.
3. Do not expose an absolute data directory in ordinary settings. Show a product phrase such as “local workspace data (managed by the application)” and reveal the path only through an intentional advanced action.
4. A route may retain a development-compatible URL such as `/workspace`; route compatibility does not justify displaying the repository codename as the product brand.
5. Static prototype values (health percentages, service states, jobs, model names) must be replaced by live APIs or clearly labelled demonstrations before calling the screen a real program interface.

## Prototype-to-runtime conversion

Convert a useful prototype incrementally rather than rebuilding it or claiming all screens are live:

1. Serve the chosen product shell from the real application route while preserving existing APIs.
2. Runtime UI assets must belong to the installed application package, not a repository-only prototype/docs directory. Declare package data, build a wheel, inspect its members, then install/run from outside the source checkout so editable imports and current working directory cannot hide missing assets.
3. Use a strict asset allowlist (for example, only `styles.css` and `app.js`) rather than a broad filesystem mount when the asset set is tiny; test traversal/unlisted assets fail closed and missing assets return 404 rather than a generic 500.
4. Wire one high-value action end to end first—normally URL/file intake—and keep all internal receipts server-generated.
5. Render only response fields the server actually returned. Never invent fallback engine names, formats, lengths, counts, or success metadata for a response class that does not carry them. At request start, clear the previous result and show a processing state; catch transport, parse, and HTTP failures and replace the whole projection with a readable failure state.
6. Verify the real application route in a browser, not only a separate static preview server; after removing inline handlers or moving scripts, exercise the changed interaction rather than checking only that HTML loads. Include success responses with optional fields absent, network failure after an earlier success, retry, and malformed/unknown route hashes.
7. Treat HTTP 200 as transport success, not schema truth. Validate the product status schema, required groups, and value types before rendering. A partial or wrong-typed 200 must clear every dependent projection—including capability panels—and show unavailable, never coerce missing data to zero or retain an old green value.
8. Route browser hashes through a fixed allowlist and select page elements with `getElementById` (or another non-selector construction). Never interpolate an untrusted hash into `querySelector`; malformed hashes must safely resolve to the unavailable page without a console exception.
9. Mark remaining demo panels honestly until their data sources are connected. Remove invented model names, service health, notification counts, and Job counts instead of letting prototype values masquerade as runtime state.
10. For local-first products, do not import fonts, scripts, analytics, or UI assets from remote CDNs. Bundle them locally or use deliberate system fallbacks. Add a restrictive CSP (`script-src 'self'`, `connect-src 'self'`, no framing/objects) and migrate inline script handlers before claiming the shell is hardened.
11. **Add a Job Center as a strict projection, not a workflow console.** Begin with a read-only history page only after Job, Outbox, and command-receipt rows have durable storage. On every read, validate their one-to-one bindings, deterministic IDs/event naming, payload equality, and receipt result before projecting a row. Return only activity label, user-facing state, delivery state, and timestamp; never send internal IDs, payloads, correlation/causation values, or lease tokens to the ordinary browser. Register collection routes before dynamic item routes (for example `/api/jobs` before `/api/jobs/{job_id}`), validate the response schema in JavaScript before rendering, and fail closed to an unavailable state on malformed 200 responses. Do not show progress bars, “running” states, or a connected dispatcher unless a real worker and event consumer have been configured and verified.
12. **Keep capability copy precise.** A read-only Job Center does not mean an interactive Job Center, and a lease-fenced dispatcher library does not mean automatic delivery is connected. Update UI, README/status documentation, and release capabilities together; preserve unimplemented capability markers until the next effectful seam is truly wired and evidenced.

See `references/product-shell-to-runtime.md` for the reusable FastAPI/product-shell tracer pattern. For the stricter installed-wheel, localhost-CSRF, collector-provenance, same-transaction Job/Outbox, and derived-effect replay recipe, load `references/durable-local-intake-and-packaged-ui.md`. For a dedicated Windows Tauri shell that supervises an isolated Python/FastAPI runtime, uses token-bound readiness and graceful stdin shutdown, blocks public navigation, and preserves the product-DTO/internal-ID boundary, load `references/windows-tauri-python-product-shell.md`.

## Installed-format release audit

When auditing whether a packaged desktop product can import the formats named by a task pack, never infer user-facing support from adapter registration, extension detection, unit tests, CI adapter groups, or a green wheel smoke alone. Build a per-format matrix with separate evidence columns for: (1) format detection, (2) product dispatch route, (3) declared product-runtime dependency, (4) system/executable dependency, (5) staged bundle membership, (6) real sample conversion, (7) durable intake/job/receipt readback, and (8) fresh installed/portable runtime replay. The strict result is the minimum of those columns; an absent cell is `UNVERIFIED`, not PASS.

Read the final wheel's `METADATA` and the installer/portable staging manifest, not only `pyproject.toml` or the CI environment. A dependency in `ci-adapters` proves test-environment availability, not product availability. Optional extras must be declared in the product runtime when the format is claimed (for example, a PDF converter's optional extra), and external tools such as OCR engines or FFmpeg must be either bundled and exercised or reported as explicit dependency-required/unavailable capabilities. Real binary fixtures are mandatory for binary formats; extension-only or plain-text files renamed to `.pdf`/`.docx` are contract tests, not conversion evidence. To *generate* genuine binary PDFs for a format-corpus audit (including CJK), see `references/real-pdf-corpus-generation.md` — the reportlab+pypdf recipe (injected via `uv run --with`, never committed) covering text/multipage/CJK/encrypted/scanned/corrupted variants, plus the two Oracle gotchas: CJK needs the `STSong-Light` CID font (Helvetica silently drops CJK glyphs), and a synthetic "scanned" sample must carry no text layer.

For the full "extra declared → lock digest synced → installed runtime converts a real binary → restart readback" closure, including the trap that changing a dependency string breaks CI tests asserting the old string, the `powershell.exe` (5.1) `-Form` limitation, and the CRLF-only-worktree-diff false positive, see `references/dependency-extra-installed-runtime-closure.md`.

Keep four verdict layers separate: source route exists; isolated runtime can convert; installed/portable artifact can convert; full user-facing intake persists and reads back after restart. A browser upload of one TXT file cannot inherit coverage for PDF, Office, image, audio, video, or URL adapters. Record unsupported and not-implemented formats explicitly instead of accepting them in the picker and returning an ambiguous generic failure. Add visible detected-format, engine, warning, and next-step output to the import result so users are not told that a registered route is necessarily usable.

For a desktop product whose frontend is still changing, retain NSIS as the formal user distribution and use a versioned portable package for internal preview/dogfood. Portable packaging changes installation/data-root behavior; it does not repair missing conversion dependencies, console subsystem/lifecycle defects, or unverified format support. Bundle frontend and backend from one exact source identity, keep the intake DTO/API backward-compatible while iterating on layout, and never let a portable preview or a frontend-only sync stand in for a verified public release. See `references/installed-format-release-audit.md` for the matrix and evidence template.

## Product-chain adapter routing

When adding a URL-specific adapter (for example transcript extraction), route recognized hosts to the adapter **before** generic HTML fetching. Use a normalized hostname allowlist (`urlsplit(...).hostname`, strip a trailing dot, case-fold), invoke the adapter through the existing `AdapterInput` contract, and return a successful `AdapterResult` directly. If the adapter is unavailable or returns a non-success result, preserve the existing safe generic fallback rather than claiming support or making the generic path unreachable.

Prove this with a RED→GREEN product-boundary test that monkeypatches the adapter, asserts the exact source URL received, asserts returned content and engine, and would fail if generic SafeHTTP runs first. Keep adapter-level tests separate from product-chain reachability evidence. For session-specific routing examples and the minimal test shape, see `references/url-adapter-product-routing.md`.

## Intake implementation sequence

1. **Discover before building.** Inspect existing URL conversion, file conversion, OCR, ASR/video, storage, and ingestion functions. Reuse them instead of building parallel converters.
2. **Define honest support.** Enumerate only formats backed by installed, exercised converters. Do not label audio/video as supported merely because a file picker accepts them or `ffmpeg` exists.
3. **TDD the public boundary.** Add tests for:
   - an accepted URL returning a conversion result;
   - a multipart file upload returning detected format, engine, and converted text;
   - empty, oversize, and unsafe filenames failing clearly;
   - page HTML containing source-oriented controls and not backend identifiers.
4. **Keep uploads local and scoped.** Store uploads beneath the runtime data directory (or another project-local ignored directory), use a generated storage name plus sanitized basename, impose a byte limit, and delete or explicitly ledger failed/orphaned conversions. Preserve both raw-byte identity and derived-text identity when conversion changes representation; do not pretend a Markdown hash proves which PDF/image bytes produced it.
5. **Persist source truth before claiming closure.** A source class must retain the provenance it can actually prove: URL collection should preserve final URL, media type, retrieval time, raw payload hash/length and extractor identity; uploads should bind raw hash to derived content. Dispatch validation by an explicit collector/payload role instead of weakening a stronger source-specific validator.
6. **Add durable orchestration without fake asynchrony.** If the import returns a Job/receipt, create the domain graph, Job row, and Outbox/audit event in the same database transaction through a migration-owned schema. A first version may be a synchronously completed durable Job, but must support strict independent read-back; never reuse an in-memory scheduler or an unrelated agent/sleep ledger as product Job storage.
7. **Return a compact result contract.** Initial mutation responses should contain display metadata, status, warnings and durable references—not an entire sensitive document by default. Read Job results by strictly reloading the referenced domain package rather than trusting an opaque `result_json` cache.
8. **Prove command replay through derived effects.** Same idempotency key plus same semantic input returns the original result without additional source, snapshot, Job, Outbox, mastery, or candidate rows. Same key plus different semantic input fails with a conflict and zero writes. Idempotency at only the first insert is insufficient if downstream snapshots keep multiplying.
9. **Exercise the actual page.** Start the local service, use a real multipart upload of a harmless local fixture, verify the returned conversion/persistence output, close the producer, then read the same Job/package through a new client or connection. Run targeted and full project gates afterward.

## Product UI must be a real design-system shell, not a bare preview page

A functionally working screen is not the deliverable. This user's explicit, twice-repeated rejection: a bare table/preview page with no visual shell reads as "没有外壳 / 普通后台 / 模板感" and is treated as unfinished, even when the data, routes, and HTTP 200s all work. A read-only dashboard or product screen must ship wrapped in a deliberate design-system shell from the first build, not as a later polish pass.

The approved visual language (see memory): **Apple + Linear + Vercel (+ Sentry for dense panels)**. Concretely, a dashboard shell must include, in one page:

- **Apple glass navigation** — sticky top bar with `backdrop-filter: saturate(180%) blur(20px)` over `rgba(0,0,0,.7)`, a brand mark + name, and a right-side status chip.
- **Hero band** — small mono uppercase eyebrow, a large dark headline with negative letter-spacing and near-tight line-height, a muted one-line subtitle, and read-only/endpoint pills.
- **Precise dark metric cards** — `#08090a` canvas, translucent panels `rgba(255,255,255,.02–.05)`, indigo accent (`#5e6ad2`/`#7170ff`), a 590-weight value, mono uppercase micro-labels, `font-feature-settings:"cv01","ss03"`, `tnum` numerals.
- **Vercel restraint** — shadow-as-boundary instead of heavy borders; whisper-level opacity shadows only.
- **Sentry-style dense panels** — status pills (FULL/PARTIAL/UNKNOWN), colored quality dots, stat rows.
- **Apple light band** — one light-gray (`#f5f5f7`) section to create the black/light rhythm.
- **Mono technical footer** — page-level read-only/mutation-surface truth and the GET endpoints.

**Do:** use system font stacks (no remote CDN fonts — local-first); `clamp()` for fluid hero/metric sizing; responsive grid that collapses 4→2→1 columns.

**Language:** this user runs Chinese (`display.language: zh`). All user-facing shell labels must be Chinese — nav chips, hero headline, metric card labels, panel titles, table headers, stat rows, footer. Keep **only** technical mono labels and data values (endpoint routes, `source-exact`/`partial` quality tokens, `telemetry.summary` event types, task IDs) in English — those are data/schema identifiers, not UI copy, and translating them breaks machine readability. A bare "please translate" should be implemented immediately across the whole shell, not deferred.

**Don't:** ship a plain `<table>` on a default background and call it done; use purple gradients; default to an admin-template card grid. When a vision model is unavailable, capture a screenshot path for the user to eyeball and ask for directed feedback instead of guessing.

When generating a design-system shell, load the `popular-web-designs` skill templates (`apple.md`, `linear.app.md`, `vercel.md`, `sentry.md`) for exact token values — but that skill is bundled; the shell is assembled here in the project.

## UX baseline

A minimal first screen should contain:

```text
[ Paste webpage URL                       ] [ Extract ]
[ Choose file / drag file here             ] [ Import  ]

Detected: PDF · Engine: markitdown
Result: extracted text preview, status, warnings, next automatic action
```

For a mature UI, add queue/progress/history later; do not block the first usable source-to-text loop on a dashboard, manual command console, or generic workflow engine.

## Information architecture for local intake

A working ingestion API is not a usable product path if the action exists only on the overview/dashboard page. Keep the source-to-intake action discoverable throughout the real product shell:

1. Put one plainly labelled, persistent action such as **“导入资料” / “Import material”** in the global header or another stable shell location. It must open the same verified URL/file intake dialog from every supported page.
2. Add contextual calls to action on relevant empty states and settings, but do not make a user navigate back to a dashboard just to begin an import.
3. Primary navigation must contain only routes with a real, user-relevant projection or operation. Do not present planned, unavailable, agent-console, workflow-builder, or connection placeholders as peer product modules; keep them out of the ordinary shell until they have a live, verified product seam.
4. A visible **Settings** route must render actual preferences that are wired to current behavior (for example theme selection persisted locally). Do not route it to a generic unavailable shell. Conversely, do not pretend to expose data-location, account, or remote-provider controls that are not implemented.
5. Browser regression tests must enter a non-overview page and assert that the persistent import control is visible and opens the real dialog. When a global and contextual control share a label, scope locators to `header`, the active page, or another semantic container; a broad text selector will become ambiguous and can mask regressions.
6. Verify both the accessibility tree and a rendered desktop viewport: the user should be able to distinguish primary navigation, current-section navigation, page content, and contextual actions without planned modules flattening the hierarchy.

## External Obsidian/source-directory safety and staged validation

When a user supplies a copied Obsidian vault or learning-material directory for testing, treat it as an untrusted, read-only source layer—not as an application workspace:

**Separate the source repository from the product black-box test root.** When a user names a directory such as `D:\\All projects\\ceshi` for unpublished real-version testing, keep the canonical source/build project elsewhere (for example `D:\\All projects\\Cognitive-Loop-OS`). The test root may contain the installer/portable candidate, isolated app data, reports, and a read-only `Obsidian知识库` input subtree; it is not a second source checkout. Never infer that the presence of a material subtree means the unpublished product artifact is already present—inventory the test root and build/copy a versioned internal preview explicitly.

1. Inventory paths, extensions, sizes, and counts before reading content. Exclude `.obsidian/`, plugin/config directories, scripts/executables, environment files, dependency manifests/lockfiles, credential/secret-named files, runtime/data/cache/log directories, and deployment/readme instructions unless the user explicitly asks to inspect them.
2. Read only a small representative set of clearly educational files first: a course overview, one substantive lesson/transcript/notes file, and (if present) a review/practice file. Do not execute source scripts or inherit source paths, environment variables, plugins, dependencies, credentials, or configuration.
3. Copy only the selected learning files into `<project>/.hermes/task-runtime/<source-test>/input/`; never write back to the source directory. Use the product's real upload/intake UI or HTTP path against those isolated copies, not direct database inserts.
4. Validate in stages: (a) one file parse/intake, (b) one file durable Job/Outbox/receipt readback, (c) a small same-course batch, then (d) Research → Knowledge → Learning only on the corrected/current runtime. Preserve incomplete answers and source uncertainty as data; never invent missing course content.
5. When a batch passes for the first file but later files fail with `checkpointed database` or SQLite `-wal/-shm` sidecar errors, classify this as a runtime read-path/WAL checkpoint boundary failure, not source contamination or content parsing failure. Record the exact HTTP/status/error and stop widening the claim until the correct current runtime is used.
6. Keep a machine-readable report under project-local ignored runtime data containing source boundary, excluded classes, selected relative paths, per-stage PASS/BLOCKED results, and the reason for every block. Do not put secrets or full source text in the report.

See `references/external-obsidian-readonly-ingestion.md` for the staged recipe and evidence schema.

## Vault write with expected-hash optimistic lock (C4-safe round-trip)

When a local-first product gains a write path back into a user Vault (H3
round-trip), implement it as a fail-closed optimistic-lock write, not a plain
overwrite:

1. **Reject before touching disk:** non-existent target, `relative_path`
   escaping the approved root (`path not in target.parents`), and binary
   payloads (e.g. ZIP magic `PK\x03\x04`) all raise 422.
2. **expected-hash gate:** hash the current file bytes; if `expected_hash`
   is provided and mismatches, raise a dedicated conflict error carrying the
   current hash → HTTP 409 (never 500, never silent clobber). Client must
   re-read before retrying.
3. **Backup before replace:** write the current bytes to a timestamped
   `.bak` under the store boundary (`<store>/vault-backups/`) so every write
   is revertible; return `backup_path` + `revert` instruction in the response.
4. **Atomic replace:** write a sibling temp file (`tempfile.mkstemp` in the
   target's parent) then `os.replace` — atomic on the same volume; on any
   exception unlink the temp and re-raise.
5. **Exception mapping:** in the FastAPI router, catch the domain conflict
   → 409 with `{"message", "current_hash"}`, catch `ValueError` → 422.
   Do not funnel the conflict through a generic `_command_error` that maps
   `ValueError → 422`, or conflicts become 422 instead of 409.
6. **Tests:** update+backup path, stale-hash conflict (409, file unchanged),
   roundtrip with fresh hash, escape/binary/missing rejection. On Windows
   write fixtures with explicit `newline="\n"` so LF expectations don't break
   on CRLF.

This pattern is implemented in `app/workspace/vault.py::write_file` +
`POST /workspace/api/vault/write` (PR #90).

### Frontend wiring: editor holds the expected hash

The C4 round-trip UI must mirror the lock on the client (PR #91):

1. **Open captures the disk hash.** When the user opens a file into the
   textarea, store `payload.source_hash` from the read response in client
   state (`state.vaultOpenHash`) and keep the editor's save button disabled
   until a file is open. Show a short hash prefix as the opened-file status.
2. **Save sends the held hash as `expected_hash`.** On success the response
   returns the NEW `source_hash` — overwrite the held hash with it, so a
   second save in the same session continues to lock correctly.
3. **409 is a user-facing conflict, not a failure.** Read `detail.current_hash`
   from the 409 body and render a message like "文件已在磁盘被修改…已拒绝写入，
   请重新打开"; do NOT clobber. After a conflict, the held hash must be cleared
   or the user must re-open (the stale hash can never succeed again).
4. **Wire the two actions in the click dispatcher** (`data-action="vault-open"`
   and `data-action="vault-save"`) alongside the existing inspect/search
   handlers; a missing dispatcher branch silently leaves buttons dead.
5. **Update the page list after a successful save** (re-run inspect) so the
   file tree/loss report reflect the new content hash.
6. **Verify in the real running service**, not only TestClient: start the app
   via its entrypoint, open → write with correct hash (200 + backup path) →
   write with stale hash (409 + `current_hash`) → read back unchanged. On
   Windows, confirm NO zombie uvicorn from a prior run is still LISTENing on
   the port before trusting that the running service has your latest code
   (see `windows-development-environment` for the `taskkill /F /PID` recipe);
   a leftover old-code server makes a correct new route look broken.

### Backup list/restore (revertible round-trip, PR #92/#93)

Extend the write path with revertible restore so every write AND every
restore can be undone (C4-safe round-trip closure):

1. **Backup placement pitfall (WinError 183):** the `store` parameter is the
   SQLite database FILE path — the backup directory must be
   `store_path.parent / "vault-backups"`, NEVER `store_path / "vault-backups"`.
   The latter runs `mkdir` on an existing file and dies with
   `FileExistsError: [WinError 183] ... cognitive_os.sqlite` on the first
   write, with a traceback pointing at `pathlib.mkdir` that looks nothing
   like the real cause.
2. **`list_backups(store, relative_path)`:** glob `{target_name}-*.bak` in the
   backup dir, sort `reverse=True` (newest first), return
   `backup_name / file_size / modified`. Newest-first ordering matters — the
   UI lists "restore to newest state" naturally.
3. **`restore_backup(root, store, relative_path, backup_name)` — three guards + revertible:**
   - traversal guard: resolve `backup = backup_dir / backup_name`, require
     `backup.parent == backup_dir` (exact filename, no `../`), AND the name
     matches `{target_name}-*.bak` (the backup belongs to THIS file). A
     foreign/`../` name → 422, never a read of an arbitrary path.
   - path guards same as write: root must be a dir, `relative_path` must stay
     inside root, target must exist.
   - **pre-restore snapshot:** BEFORE replacing, write the current on-disk
     bytes to `{target_name}-{stamp}.pre-restore.bak` and return its path —
     the restore itself is revertible, and the response includes
     `restored_from` + the new `source_hash`.
   - atomic replace via sibling temp + `os.replace`, same as write.
4. **API + UI wiring:** `POST /api/vault/backups` (list) + `POST
   /api/vault/restore` (restore). UI: 备份列表 button fills a `<select>`,
   恢复选中备份 button POSTs the exact `backup_name`; after a successful
   restore, RE-READ the file and refresh the editor content + held hash +
   file tree — the held `expected_hash` must follow the restored content or
   the next save 409s.
5. **Tests:** frontmatter-preserved read→edit→write roundtrip (assert YAML
   properties survive), list newest-first, restore restores exact content AND
   creates the pre-restore snapshot, traversal/foreign backup_name → 422.
   Windows: write all fixtures with explicit `newline="\n"`; the C4 body
   functions do their own `import hashlib/os/tempfile/datetime` locally —
   don't assume module-level imports exist when copying the pattern.

## Explicit full-batch testing mode

When the user says “全量测试”, “不要一个一个试”, or otherwise rejects representative/manual sampling, switch from staged sampling to **batch coverage mode**. Staged smoke tests may still validate the harness, but they are not the deliverable.

1. Freeze scope before intake: inventory every in-scope path, extension, byte size, and content boundary; record excluded directories/classes and the exact candidate count.
2. Build one deterministic batch manifest with relative path, byte size, content SHA-256, detected class, and exclusion reason where applicable. Do not silently narrow a supplied vault to a representative course.
3. Submit the complete manifest through the real product intake boundary (UI or HTTP multipart), never direct database inserts. Use a bounded sequential writer when the product has durable SQLite/job/outbox state; do not create concurrent writers to speed up a batch.
4. Respect product rate limits rather than bypassing them with forged proxy headers, invented credentials, parallel identities, or middleware/config tampering. Read `Retry-After`, persist progress incrementally, and resume from the manifest using content identity.
5. Record one machine-readable result per candidate, including PASS, BLOCKED, rejected/unsupported, transport error, retry count, and exact sanitized reason. “Attempted all” is a coverage claim; it is not a success claim.
6. If a deterministic systemic failure repeats, continue the full batch when feasible so the final report proves coverage, but distinguish the root-cause sample from the aggregate count. Never convert unattempted files into inferred results.
7. Only run downstream delivery/Research/Knowledge/Learning stages when intake produced valid durable candidates. If every candidate is blocked at a shared gate, report downstream stages as NOT EXECUTED rather than fabricating projections.
8. Validate final coverage: `candidate_count == result_count`, no duplicate/missing manifest identities, report file is readable, source tree remains unchanged, only the project-local ignored runtime was written, and owned processes are stopped.

For the full-vault batch manifest/result schema, rate-limit-respecting writer, repeated-gate classification, and evidence checklist, see `references/full-batch-readonly-material-ingestion.md`. For the live-WAL versus immutable-checkpoint boundary, real-sample-before-batch gate, durable restart readback, evidence labels, and fixture restoration, see `references/live-wal-full-batch-closure.md`.

## Content-addressed document byte serving (e.g. PDF.js reader)

When a reader needs the original binary (PDF.js needs PDF bytes; a Word/image viewer needs the DOCX/PNG), serve it by content hash over an HTTP endpoint — never by a storage path, and never via an index that reveals where the file lives.

1. **Backend module** (`app/evidence/pdf_serve.py` style): `store_pdf_bytes(root, blob) -> "sha256:<hex>"` and `resolve_pdf_bytes(root, content_key) -> bytes`. Reject empty/oversized blobs; reject any content key not prefixed `sha256:` (fail-closed). Bound size (e.g. 50 MB). Back it with the RawAsset store so it is content-addressed and immutable.
2. **HTTP endpoint** (`GET /workspace/api/pdf/{content_key}`): resolve via the module, return `Response(content=blob, media_type="application/pdf")`. Map `PdfServeError` to `404` (never a generic 500). Construct the serving root under the same runtime data dir as the product DB (`resolve_runtime_path("data")`), and monkeypatch `router.PDF_ROOT` in tests to a tmp dir.
3. **Real-fixture byte-fidelity test, not fabricated**: store a genuine PDF (text + images), GET it back, and assert `resp.content == blob` **and** `sha256(resp.content) == sha256(blob)` — byte-for-byte identity over the HTTP boundary. Test fail-closed separately (non-sha256 key -> 404, missing content -> 404).
4. **Fixture placement + CI safety**: keep real PDFs in the canonical workspace's runtime attachments dir (e.g. `<project>/.hermes/desktop-attachments/`), which is NOT inside any git worktree. In tests, reference the absolute path and `pytest.skip(...)` when the file is absent. CI without local fixtures therefore skips the real-file tests (never fabricate a fake PDF by renaming a text file). This also satisfies "real binary fixtures are mandatory for binary formats" — a 322-page illustrated PDF and a 120-page text PDF exercised end-to-end are real evidence.
5. **Runtime-level closed loop, beyond TestClient.** A unit/HTTP test proves routing; it is not the same as the live service. To prove the endpoint works in the real running app: (a) migrate the runtime DB first — a schema-gated FastAPI core refuses to start until migrated, so run `python -m app.runtime_entrypoint migrate` (applies every sqlite owner: core/knowledge/research/sleep/taskpack/workspace) before launching; (b) start the app through its own entrypoint, not bare uvicorn — `python -m app.runtime_entrypoint core` (bare `uvicorn app.main:app` dies with `SQLite schema has not been migrated` because the app's lifespan calls `core_runtime_guard(validate=validate_schema)`); (c) seed the fixture into the serving root, then `curl -D - -o <tmp> "http://127.0.0.1:8000/workspace/api/pdf/<sha256:key>"` and assert `HTTP 200`, `content-type: application/pdf`, exact byte count, and `sha256sum(curl_out) == sha256(original)`. Two real PDFs (18.9 MB + 2.2 MB) both returned byte-identical hashes this way. On Windows, write curl output to a native path (`C:/Users/<user>/AppData/Local/Temp/...`) because `curl -o /tmp/x` can silently produce no file via MSYS. Kill the background server afterward so no process leaks.

## Pitfalls (continued)

## Pitfalls

- **Internal-ID console disguised as a frontend:** replace it with URL/file controls and generate internal IDs server-side. When an existing engineering tracer already exposes `command_id` / `package_id` / `artifact_id` forms, treat it as a developer console, not the product frontend — add the source-material intake boundary in the same delivery, don't defer it to a later polish pass. Users experience the ID form as "too complex, not a real product", and retrofitting the intake UI afterward costs a full extra round-trip.
- **Fake media support:** if ASR, video frame extraction, or a converter has not been installed and tested, state that it is pending and reject/queue clearly rather than returning fabricated output.
- **Unbounded uploads:** reject empty and oversized uploads before conversion; sanitize names and never trust browser paths.
- **Remote unauthenticated exposure:** local-first unauthenticated write paths must be constrained to loopback. Reintroduce explicit auth before LAN/cloud access.
- **“Converted” but not usable:** after conversion, make the resulting content visible and connect it to the next automatic decomposition/persistence stage. For evidence-governed systems, a durable first slice is `converted content → content-hash SourceRecord → candidate Claim/Evidence → review-required ResearchPackage → strict second-connection readback`; preview-only conversion is not an ingestion closure.
- **Weakening source identity to add a new format:** do not remove an existing source-specific validator (for example, GitHub provenance reconstruction) to admit generic documents. Dispatch fail-closed by an explicit payload role and give each supported source class its own deterministic identity/provenance validator. Unknown or mixed role sets must be rejected.
- **Random upload path becomes identity:** storage filenames may be random, but domain identity and idempotency should derive from canonical source semantics and content hash. Never persist absolute upload paths as user-visible provenance.
- **Remote dependencies in a local-first shell:** remote font imports and CDN scripts leak network activity and can break offline startup. Bundle them or use local/system fallbacks before productizing the prototype.
- **`http.server` handler factory that forgets to return the class:** a `make_handler(store)` closure that defines `class Handler(BaseHTTPRequestHandler): ...` but omits `return Handler` silently returns `None`. `ThreadingHTTPServer((host, port), make_handler(store))` then gets `RequestHandlerClass=None` and **every request 500s** with `TypeError: 'NoneType' object is not callable` at `finish_request` — a confusing symptom that looks unrelated to the missing return. If you hit it, assert `make_handler(...)` is not None (or inspect `server.RequestHandlerClass`) before debugging routes. Always `return` the handler class from the factory.
- **Demo data must go through the module's own sanitizing adapters, not raw dicts.** When a strictly read-only observer/dashboard needs sample rows, feed events via its validated adapter functions (e.g. `workflow_evidence_events`, `token_usage_events`, `telemetry_events`) so schema + redaction are enforced; raw hand-built event dicts bypass the fail-closed validation the pipeline depends on. Note the valid evidence states are `NOT_RUN / PASS / FAIL / BLOCKED / UNVERIFIED / SKIPPED_OPTIONAL` — `PARTIAL` is not accepted and raises `ObserverInputError`. Demo events persist under the project's ignored runtime path (never committed), and the page rebuilds its projection from the event store on every request, so writing then re-fetching the page shows them immediately.
- **A "single transaction" that mixes a byte-file write with SQLite rows is not atomic.** When a RawAsset-first durable import writes a content-addressed original file AND inserts job/outbox/receipt rows inside one `BEGIN IMMEDIATE`, a conversion failure (or a same-command-id idempotency conflict) rolls back the SQLite side but **leaves the just-written byte file orphaned** — no DB row references it, so a later GC/quota pass can't distinguish it. SQLite-side "0/0/0 on rollback" is NOT the whole story. Track a `wrote_original` flag set after the file write and, on any exception, delete that digest's file; do this for the **conversion-failure AND the idempotency-conflict paths** (the conflict path writes a *new* digest file before raising, so it leaks too). Also unify the error contract: a store-original write failure (`RawAssetStoreError`) must surface as the same `ImportJobError` the caller catches, or the caller will miss import failures. Independent read-only review caught exactly this class of bug; see `references/rawasset-import-transaction-parity.md`.
- **Adding a field to a strict (`extra="forbid"`) versioned contract silently breaks legacy round-trips.** When you extend a Pydantic contract (e.g. add `scope: str | None = None` to a unit model), `model_dump()` carries the new field but a hand-written legacy adapter row dict and its `_ROW_FIELDS` allowlist do not — so `to_legacy_row()` can silently drop the new field. On a read-only review this surfaces as a "WARNING: lossy round-trip", which is easy to wave off because the current lifecycle statuses happen to prevent the scoped value from reaching that path. Do not rely on that accidental shielding: fail closed in the adapter (raise a `ContractMappingError` if the new field is non-default on a legacy path) and add an explicit behaviour assertion. The same rule applies to any new JSON-serialized object that has an alternative legacy representation — audit every round-trip site when you add a field, not just the primary schema.\n- **The product intake DTO often carries no durable job_id.** A clean product response (`WorkspaceIntakeResult`) exposes `source_type`, `format`, `engine`, `char_count`, `requires_human_review` — but NOT the internal `job_id`/`command_id` (that's the point of the DTO boundary). When verifying durable persistence from an installed runtime, do not read `resp.job_id` (it will be null/missing); instead query the durable projection separately (`GET /workspace/api/jobs`) and match the job by content/source. In a PowerShell/HTTP install-state check this trips as `restart port missing` or a null job handle; re-wire the verification to fetch the jobs list, capture its job id, then assert restart readback (`restart_has_original_job == true`) against the same projection after the process restarts.
- **A `store` param holding a FILE path breaks `<store>/subdir` mkdir with WinError 183.** When a write/backup helper receives the SQLite DB path (a file, e.g. `data/cognitive_os.sqlite`) as `store`, deriving a backup dir as `store_path / "vault-backups"` calls `mkdir` ON the existing database file → `FileExistsError: [WinError 183] 当文件已存在时，无法创建该文件` on first write, and the traceback points at `pathlib.mkdir` with the DB path — looks like a storage bug, is really a parent-path bug. Use `store_path.parent / "vault-backups"`. Also: local per-function imports (`import hashlib/os/tempfile/datetime`) are fine inside these helpers but don't copy a helper and assume its imports are module-level; a fresh helper missing `datetime` fails with `NameError` at runtime.

## Batch closure and executable-smoke pitfalls

- **Do not infer test collection from a test filename.** Some browser/lifecycle matrices are tracked as executable smoke scripts with `main()` and assertions but no pytest functions. Running `pytest path/to/script.py` can correctly return `no tests ran`; inspect the module before classifying it, then run the documented direct script entry under the clean project environment. Restore any fixture the script creates or rewrites before reporting workspace cleanliness.
- **Gate full-batch intake on a fresh-database real-sample closure.** Before submitting a large manifest, create a new isolated runtime database, prove one harmless source through intake → durable delivery receipt → Research → Knowledge → Learning → practice/mastery, restart the same runtime against the same database, and read the durable state back. Only then start the rate-limited batch. This separates runtime/schema regressions from source-level failures and prevents a long batch from producing unusable evidence.
- **After live-WAL fixes, use two explicit read modes.** Internal runtime projections may use a query-only live-WAL reader; offline/checkpoint consumers must retain the immutable checkpoint-only guard. Do not globally weaken the offline reader merely to make an in-process approval path pass.
- **Treat delivery as a separate, rate-limited batch stage.** A successful HTTP intake and succeeded Jobs do not imply delivered Outbox rows or recorded receipts. Measure `intake → jobs → outbox → receipts` independently. Dispatch endpoints may share the product's sensitive-write limiter; a tight loop can return throttled responses while leaving most rows pending. Persist the upload report first, then drain delivery with the documented interval (for this runtime, about 2.1 seconds per dispatch), inspect each response/status, and only claim closure after pending=0 and receipts=recorded for the durable job set. Never re-upload merely because delivery is pending.
- **Do not trust a truncated final process log.** When a long batch exits with output clipped at the tail, read the machine-readable report and query the live API/database separately. Reconcile `candidate_count`, per-file result count, job count, outbox state, and receipt state; an exit code of 0 proves only the batch script's own terminal condition, not downstream delivery closure.

## Verification checklist

- [ ] Page has URL/file intake controls and no user-entered command/package/artifact IDs.
- [ ] API key/JWT widgets are absent in explicit local-first mode.
- [ ] URL conversion uses the existing safe HTTP policy.
- [ ] Multipart upload stores only under the intended local runtime area.
- [ ] A real text/file upload is exercised through HTTP.
- [ ] Unsupported audio/video is explicitly reported as unsupported/pending until a real pipeline exists.
- [ ] Targeted tests, formatter/linter, architecture guard, and full test suite pass.

---
name: sqlite-schema-migrations
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/sqlite-schema-migrations/SKILL.md
---

---
name: sqlite-schema-migrations
description: Safely evolve SQLite schemas with recorded migration provenance, exact schema validation, rollback backups, and test-first compatibility upgrades.
version: 1.0.0
---

# SQLite Schema Migrations with Provenance

## Use when

Use for an application-owned SQLite schema that has one or more of:

- a migration ledger (`schema_migrations` or equivalent);
- exact schema/object validation after migration;
- owner/operator provenance and backed-up rollback;
- existing user databases that must be upgraded without data loss;
- durable event, receipt, lease, or audit tables.

## Core rule

**Never modify the definition of an already-recorded migration to add a table, index, column, or constraint.**

Exact-schema validation will correctly classify existing databases as drifted if an old migration's expected DDL changes. Add a new versioned migration instead.

## TDD sequence

1. Read the schema owner, registry/operator, migration ledger, rollback validator, and existing migration tests.
2. Write a RED test for the new object on a fresh database.
3. Write a second compatibility test that constructs/applies the recorded prior schema, then asserts only the new migration is applied.
4. Run both tests and confirm the expected missing-object or pending-upgrade failure.
5. Implement the smallest extension migration.
6. Run the focused migration suite, then changed-file lint and whitespace checks.

## Incremental migration design

For a v1 schema receiving a v2 extension:

1. Preserve the v1 DDL exactly.
2. Add a separate migration version and stable name for v2.
3. Define v2 DDL separately (for example, a table with a foreign key binding a durable receipt to an outbox event).
4. Track recorded migration names/versions as a set, validating exact version/name pairs and prerequisites.
5. Build expected schema objects conditionally from the recorded migration set:
   - v1 recorded: validate only v1 objects;
   - v1 + v2 recorded: validate v1 plus v2 objects.
6. Make pending detection return the exact missing migration names in dependency order.
7. In one `BEGIN IMMEDIATE` transaction, back up, apply only pending DDL, insert only their ledger rows, revalidate the recorded schema, then write operator provenance.
8. Make backup provenance identify the **actual applied migration set** (for example, joined names), not a hard-coded original migration name.
9. Update owner version/target only if the operator identity must represent the latest schema; confirm registry status/apply behavior first.
10. Update rollback validation allowlists to accept the known migration set, while retaining strict subset/exact provenance checks.

## Durable outbox consumer pattern

For an outbox event that must not be falsely marked delivered:

- Pass `event_id`, `event_type`, and canonical payload to the handler.
- Require a structured confirmation bound to the same `event_id` and a non-empty proof.
- Treat `None`, empty objects, mismatched IDs, or missing proof as failures, never delivery success.
- For a local consumer, validate the event is still leased and its stored type/payload equal the claimed event before recording the effect.
- Persist a unique event-bound receipt (`event_id` primary key/foreign key, consumer identity, canonical proof, timestamp) in the consumer transaction.
- Keep lease-fenced terminal state transition in the dispatcher transaction after the handler returns.

## Capability-level read-only mode for projections (no migration, no WAL)

A strict read-only projection (e.g. an observer that must never mutate the
writer's store) breaks its contract the moment it opens the store through the
normal constructor: the store class typically runs `_ensure_schema()` /
`_migrate()` (CREATE TABLE + ledger INSERT) and sets `PRAGMA journal_mode=WAL`
— all writes, on every open. Do not fix the caller with a "don't call
migrate" flag; give the store an explicit read-only mode:

- Open with a URI: `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` —
  any accidental write then raises `OperationalError: attempt to write a
  readonly database` (fail closed at the engine, no per-method guards).
- In read-only mode: do **not** `mkdir` the parent, do **not** run schema
  migration, do **not** set WAL — `SELECT`s (including version/seed reads)
  still work, and the projection cannot drift the schema ledger.
- Fail closed on missing file: raise instead of creating an empty DB.
- Bind the policy in the constructor signature (`readonly: bool = False`),
  and assert it in tests: a write method against the read-only handle raises.

This keeps migration provenance (writer side) and projection purity (reader
side) separated: the reader is capability-bound, not policy-reminded.

## Verification checklist

- Fresh database receives all required schema objects.
- Recorded prior database receives only the new migration.
- Reapply is idempotent.
- Recorded schema drift still fails closed.
- Rollback provenance includes and validates the exact migration set applied in that operator run.
- Consumer success creates a receipt before outbox delivery confirmation.
- No-op, invalid confirmation, receipt conflict, payload mismatch, and lease loss cannot become `delivered`.
- Run focused migrations + consumer/dispatcher tests, lint, and `git diff --check` before broader gates.

## Pitfalls

- Do not use a worker checkpoint as a per-event delivery receipt; it is usually upserted and cannot prove durable handling of each event.
- Do not loosen schema validation to accept arbitrary extra owned tables; this masks corruption/drift.
- Do not change rollback checks from exact/known-set validation to unconditional acceptance merely to support a new migration.
- Do not call a handler successful solely because it did not raise.


## 合并来源: sqlite-migration-governance (2026-08-21 合并优化)

---
name: sqlite-migration-governance
description: Safely evolve SQLite schemas governed by exact schema validation, migration provenance, backups, and rollback receipts.
version: 1.0.0
---

# SQLite Migration Governance

## Use when

Use for a repository that has one or more of:

- recorded SQLite migration versions/names;
- exact validation of table/index SQL against expected definitions;
- migration-owner provenance and rollback backups;
- a requirement to upgrade existing user/runtime databases without destructive rebuilds.

This skill is especially important when adding a table, index, constraint, or receipt to an already-shipped SQLite owner.

## Core rule

**Never edit the definition of a schema that existing databases have already recorded as applied.**

If a v1 owner validates its recorded schema exactly, modifying its original `CREATE TABLE` SQL turns every existing v1 database into apparent schema drift. Add a separately named, versioned incremental migration instead.

## Safe incremental-migration workflow

1. **Map the ownership boundary before editing.**
   - Find the owner registry entry and its version/target/kind.
   - Find the migration-version/name constants.
   - Find the owner module's `status`, `migrate`, schema validation, and the migration operator's rollback provenance checks.
   - Find fresh-apply, drift, rollback, and migration-owner tests.

2. **Write one RED test first.**
   Start with the smallest externally observable schema contract, for example asserting the new receipt table and exact columns exist after owner apply. Run only that test and verify it fails because the feature is missing.

3. **Add an additive migration identity.**
   - Allocate a new globally unique migration version and stable migration name.
   - Keep the v1 schema SQL unchanged.
   - Put new tables/indexes/columns in a separate extension SQL block.
   - Add the new migration name to any backup-manifest / rollback allowlist.

4. **Make validation version-aware.**
   - Read all relevant recorded migration rows, rejecting version/name collisions.
   - Reject an extension migration recorded without its prerequisite.
   - Validate v1-only databases against the v1 object set.
   - Validate v2 databases against v1 plus extension object sets.
   - Treat unknown owned objects or any mismatch as fail-closed drift.

5. **Apply pending migrations atomically.**
   - Compute the ordered pending migration names before creating the backup.
   - Create one backup whose manifest records the exact `+`-joined pending migration set.
   - Apply only missing SQL blocks and insert their individual schema-migration records in the same immediate transaction.
   - Validate the recorded post-apply schema before committing.
   - Return the exact applied names so operator provenance and rollback agree.

6. **Advance the owner contract deliberately.**
   If the migration operator uses a versioned owner identity, advance the owner version/target to represent the new durable capability. Define the **exact legitimate sets** of migrations for that owner and reject every other set during rollback. For a v1→v2 additive owner these commonly are `{v2}` (recorded-v1 upgrade) and `{v1,v2}` (fresh initialization); accepting an arbitrary non-empty subset of known names is unsafe.

7. **Verify three paths, not just fresh DBs.**
   - **Fresh apply:** creates v1 + extension and records both.
   - **Recorded v1 upgrade:** applies only the extension; preserves existing rows and original v1 SQL.
   - **Rollback:** backup manifest, operator provenance, and allowlist agree; rollback still refuses changed databases.

8. **Run layered gates.**
   Run the focused migration suite, changed-file lint, then the repository's relevant broader schema/runtime suite. For CI workflow changes, also parse YAML and test the policy fixture.

## Durable receipt design

For event consumers, a delivery receipt should be bound to the event itself:

- `event_id` is the primary key and foreign key to the outbox event;
- include `consumer_name`, canonical `proof_json`, and `created_at`;
- do not treat a worker's last-checkpoint row as a durable receipt for every event;
- do not mark an outbox event delivered until the consumer has written and read back a valid event-bound receipt.

## Lease-fenced consumer confirmation

A delivery receipt is only meaningful if it is written for the exact event currently held by the dispatcher:

1. Pass `event_id` to the consumer; event type and payload alone are not an identity.
2. Before inserting the receipt, open a short `BEGIN IMMEDIATE` transaction and re-read the outbox row.
3. Require the row to still be `leased`, and compare its `event_type` plus canonical serialized payload with the delivered event.
4. Insert the unique receipt inside that same transaction. On conflict, only accept an idempotent retry when the stored consumer/proof exactly matches; otherwise fail closed.
5. Return an acknowledgement containing the same `event_id` and a non-empty structured proof. The dispatcher must reject `None`, an empty mapping, a missing proof, or an acknowledgement for another event before its lease-fenced `delivered` update.

Test both paths: a normal delivery persists a receipt before `delivered`; no-op, malformed, or wrong-event acknowledgements become `failed`/retryable and leave `delivered_at` unset.

## Pitfalls

- **Byte hashes never verify a `VACUUM INTO` backup.** The snapshot's raw
  bytes differ from the source file's (fresh page layout), so
  `sha256(backup_file) != sha256(source_file)` by construction. Verify with
  a logical **content hash** (sorted tables × rows in rowid order, bytes and
  text tagged distinctly) and name backups after `hash[:8]` so re-running
  backup/migrate is idempotent without re-VACUUMing. Full pattern in
  `references/legacy-db-to-workspace-migration.md`.
- **Fresh-only tests are insufficient.** They can pass while recorded v1 databases become irrecoverable drift.
- **vec0 / extension virtual tables break `SELECT *` fingerprinting.** A migration operator that fingerprints every table via `SELECT * FROM "<table>"` fails with `sqlite3.OperationalError: no such module: vec0` when the connection has not loaded the sqlite-vec extension (the extension is lazy-loaded only in the vector-db module's own connection). Fix: in the fingerprint loop, skip tables whose declared SQL contains `USING vec0` or `VIRTUAL TABLE` — their rows are derived from the companion `*_id_map` table, which is fingerprinted anyway. This unblocks fresh `migrate` on a clean DB and is required before any local server can start.
- **Backup directory must live beside the DB file, not under it.** If a writer receives the SQLite database file path as its `store` argument, `store / "vault-backups"` resolves to a path under the DB *file* and `mkdir` fails with `FileExistsError [WinError 183]`. Use `store.parent / "vault-backups"`.
- **Do not weaken exact schema validation** just to permit a new table. Make expected objects depend on recorded migration state instead.
- **Keep backup manifests and operator provenance aligned — then test consistent tampering.** If an apply reports `{v1,v2}` but the backup manifest says only `v1`, rollback must fail; fix manifest generation, not rollback validation. Also mutate both the operator provenance and backup manifest to the same invalid subset (for example `{v1}` under a v2 owner) and prove rollback still rejects it before replacement. Cross-checking two mutable records is not a substitute for an exact owner-level allowed-set check.
- **Do not use a no-op handler as delivery.** A handler returning `None`, an empty mapping, or an unbound acknowledgement must not transition an event to `delivered`.
- **Do not merge CI containment with feature work.** A job-level timeout is an independent CI correctness slice; keep it separately testable and reviewable.
- **Read-only consumers must never run the writer's store constructor
  (2026-08-15, WL3-605).** A read-only projection (e.g. an Observer reading
  a workflow-owned canonical store) that opens the store with the normal
  constructor silently executes schema migration (`_ensure_schema` /
  `executescript` + `INSERT` into `schema_migrations`) and sets
  `PRAGMA journal_mode=WAL` — i.e. the "read-only" consumer WRITES the
  store it is supposed to observe. Fix: give the store a `readonly=True`
  mode that (a) opens with the SQLite URI `file:<path>?mode=ro` (any write
  then raises `sqlite3.OperationalError: attempt to write a readonly
  database` → fail closed for free), (b) skips `parent.mkdir`, schema
  migration, and the WAL pragma, and (c) refuses to open a missing file
  instead of creating it. Keep `PRAGMA foreign_keys=ON` (read-only pragma).
  The read-only consumer passes `readonly=True` at construction; add a
  regression test asserting a write method on the readonly connection
  raises. This is the capability-level read-only boundary: absence of write
  code paths is not enough, the connection itself must reject writes.
- **Identity-rename DDL drift in an existing dev DB (2026-08-13).** After a repo/product rename, contract DDL that embeds the old name (e.g. `target_repo TEXT DEFAULT 'Cognitive-OS'` → `'ArcheAxis'` in `storage.IR_KB_TABLES`) changes the *expected* contract, but the existing database keeps the old DDL — `core_schema.validate` then fails closed at startup with `baseline schema does not match core.sqlite owner: mismatched=table:<name>`, and `migrate` also refuses (the operator validates before applying). Diagnose by comparing the live `sqlite_master.sql` with `expected_contract()` (`mismatched` means same object, different DDL — typically a DEFAULT value, not a missing table). Recovery for a **dev database with zero business rows** (check row counts per table first, not just size): copy the DB to `backups/`, delete it, re-run `migrate` — the fresh DB is created from the current contract. Do NOT hand-edit `sqlite_master.sql` in place, and do NOT apply this rebuild path to any database with real rows (those need a proper versioned migration per the workflow above).
## Reference

- `references/versioned-receipt-migration.md` — concise checklist for the v1→v2 event-receipt pattern and expected tests.
- `references/legacy-db-to-workspace-migration.md` — legacy single-DB → multi-domain migration pipeline (backup → dry-run → migrate → rollback-readback) with content-hash verification, idempotent backup naming, and table-classification heuristics.

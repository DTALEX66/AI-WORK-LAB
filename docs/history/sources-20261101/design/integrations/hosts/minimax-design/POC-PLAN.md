# MiniMax Design host adapter — POC plan (DL-P0-060)

- **Task**: DL-P0-060 `MINIMAX_SECONDARY_HOST` (Deep Adaptation Master TaskPack)
- **Date**: 2026-09-13
- **Subject SHA**: `9f34b53e7eff5707e087c35bced57bb17b856ab8`
- **Current status**: `NOT_EXECUTED` — structural declaration only
- **Executor of the live steps below**: the owner or a host-capable operator, not an offline agent

## Why this is a plan and not a result

An offline agent can write the acceptance contract, but the acceptance itself
needs a running host: launching the application, driving it, exporting a real
artifact and reopening it. The user's current instruction is explicit — work
that requires actually operating a host or exercising design judgement is out of
scope for this execution. Nothing below was performed.

## Recorded facts (read-only, already in the repository)

| Fact | Value | Source |
|---|---|---|
| Application present | MiniMax Design 3.0.10 | `reports/current/MACHINE_INVENTORY.json`, `observed_at 2026-09-13T14:54:08+00:00` |
| Local data root | `C:/Users/ALEX/AppData/Local/com.minimax.hub` (path recorded as a location only) | `docs/LOCAL_ENVIRONMENT.md` |
| Model weights | MiniMax H3, four component files | separate acceptance path, see H3 许可证据交接（2026-09-13；原件已按 owner 2026-10-19 指令删除，其结论与独有事实汇总在 `docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md`，逐份 blob/restoreAt 在 `docs/history/archive-2026-10-19/REMOVALS.json`） |
| Launch performed | no | this execution |
| API called | no | this execution |
| Artifact produced | no | this execution |

Presence in this table is **not** evidence of a working host. Per `AGENTS.md`,
existence information supplied by the owner does not replace a current version,
launch, inference, readback and rollback test.

## Preconditions — all must be satisfied before step 1

1. **Owner authorisation** for the POC window, recorded with a date and scope.
2. **Rights position** for the application's terms of use confirmed by the owner
   (the declaration currently reads `license: "unverified"`).
3. **Host profile** approved by the user, as required by the installer gate used
   by the Open Design adapter — the same discipline applies here.
4. **No private-state access**: the POC must not open the host's private
   databases, account state or personal asset library.
5. **Quota/stop-line check**: the POC does not silently lift a development
   stop-line recorded elsewhere.

## POC scope — the smallest thing that proves something real

Prove one editable-delivery loop, not a feature tour:

1. Create or open **one** simple design (a single-artboard item is enough).
2. Perform one deterministic edit that can be described in words.
3. Export to a format the host claims to own, and record the exported file.
4. **Reopen** the exported file in the host and confirm the edit is still there.
5. Record the digest of the artifact **before** and **after** the reopen.

If the host cannot reopen its own export, the capability is `supported: false`
and the POC records that as the result rather than a failure to hide.

## Evidence a completed POC must contain

| Field | Requirement |
|---|---|
| `host_id`, `host_version` | exact build string, not "latest" |
| `os`, `subject_sha` | Windows build and the exact DESIGN-LAB commit |
| Actions | ordered, replayable description of every click/command, or a script |
| Artifact | path plus `sha256:<64 hex>` of the exported file and its byte size |
| Readback | `sha256:<64 hex>` of the reopened file plus what was compared |
| Failure and recovery | any error seen, its exact text, and how it was resolved |
| Rollback | what was done to return the host to its prior state |
| Four axes | `implementation`, `unit`, `host_live`, `delivery` recorded separately |

A record missing any of these is an E1 structural note, not a POC result.

## Definition of done

- The POC record exists under `integrations/hosts/minimax-design/evidence/` with
  the fields above, and `adapter.manifest.json` is updated **only** for the
  capabilities actually demonstrated, with `supported: true` limited to those.
- `evidenceLevel` moves to `E2` for a controlled run on a synthetic fixture, or
  `E3` only for a real brief → editable artifact → reopen → rollback loop.
- Anything not exercised stays `supported: false` with an honest note.

## Forbidden during the POC (unchanged project rules)

- No reading of `.env`, credentials, private sessions or the host's personal
  libraries.
- No writing outside this repository except the host's own project folders that
  the owner explicitly opens, and no writing to `E:\`.
- No silent modification of shared host configuration; process isolation only.
- No retroactive upgrade of the existing H3 evidence by anything learned here.

## Known risks

| Risk | Mitigation |
|---|---|
| The host's export format is proprietary and undocumented | treat it as an opaque external asset; a documented importer is a separate task |
| An agent drifts into "the UI looked right, so it works" | the readback digest is the only acceptance signal |
| Acceptance of the application is read as acceptance of the H3 weights | the manifest keeps the two acceptance paths explicitly separate |
| Version drift between the recorded 3.0.10 and the running build | record the running build string at run time; never reuse the recorded one |

# Cron Run Verification and Recovery Reference

Use this checklist when a durable project queue appears to stop.

## Required evidence

1. Run `hermes gateway status` and `hermes cron status`.
2. Confirm Gateway is running and cron status explicitly says jobs will fire automatically.
3. `cronjob list` must show exactly one project job, the intended cadence, `enabled=true`, `state=scheduled`, and the expected pinned provider/model.
4. Read the project `.hermes/sleep-mode/state.json` and the tail of `activity.jsonl`.
5. After `cronjob run`, verify all three layers:
   - tool result: `executed=true`, `execution_success=true`;
   - job state: `last_status=ok`;
   - project evidence: a fresh start/progress/complete ledger event and changed task/state.

A successful API response alone is not proof of work.

## Common root causes

### Gateway absent

`hermes cron status` reports:

```text
Gateway is not running — cron jobs will NOT fire
```

Start/install the user-level Gateway according to Hermes instructions. On Windows without UAC, Hermes may use a Startup-folder login item. Recheck both Gateway and cron status after startup.

### Provider/model drift guard

An unpinned job can be skipped before inference when the global provider/model changed since job creation. The execution output may contain:

```text
Skipped to prevent unintended spend: global inference config drifted since this job was created ... and this job is unpinned.
```

Pin the exact provider and model selected by the user with `cronjob update`, then rerun and verify `last_status=ok`. Do not substitute another model merely because it is available.

### Queue exhaustion

`mode=completed` with `stop_reason=queue_exhausted_all_tasks_completed` means the current queue ended; it does not prove Gateway stopped. If the user explicitly authorized continuous work, consult the live roadmap and create one evidence-backed next TaskPack. Do not fabricate task IDs or append a fake completion entry.

## Safety

- Never trigger a second cycle while state/activity show an active writer.
- Do not rewrite state or JSONL to simulate progress.
- Preserve dirty WIP and project-local evidence.
- Do not touch unrelated Hermes workflow data, external projects, credentials, or protected drives.

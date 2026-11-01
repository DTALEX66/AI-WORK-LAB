# Windows Gateway / Cron Recovery Reference

## Verification sequence

Run from the project root:

```bash
hermes cron status
hermes gateway status
hermes cron list
```

The authoritative automatic-execution signal is:

```text
Gateway is running — cron jobs will fire automatically
```

A job shown as `enabled=true` and `state=scheduled` is only registration state. If `hermes cron status` says `Gateway is not running — cron jobs will NOT fire`, automatic ticks are not occurring.

## Repair sequence

1. Read the project `.hermes/sleep-mode/state.json` and the tail of `activity.jsonl`.
2. Confirm there is no active writer-start event before starting a catch-up cycle.
3. Start the Gateway:

   ```bash
   hermes gateway start
   ```

4. If the Windows service is not installed and administrator approval is unavailable, Hermes may use a Startup-folder login item fallback. Do not treat the install output alone as proof.
5. Verify both:

   ```bash
   hermes gateway status
   hermes cron status
   ```

6. Confirm the project cron still has exactly one job, the intended workdir, and the user's cadence (for this project: 10–15 minutes, currently `every 10m`).
7. If immediate progress is requested and no writer is active, call the cron run operation once, then reread state/activity for a fresh task-start or task-complete event.

## Missed-tick diagnosis

Compare three clocks/signals:

- system time (`date` or Python datetime);
- scheduler `last_run_at` / `next_run_at`;
- project activity timestamps and task transitions.

If wall time has passed `next_run_at` but `last_run_at` and activity did not advance, classify the tick as missed/unverified. Check Gateway first. If scheduler timestamps are offset from system time, report the skew and use the Gateway heartbeat plus ledger events as execution evidence; do not infer success from a moved `next_run_at` alone.

## Single-writer guard

Never issue another manual run when the state ledger says a task is active or the activity tail contains a start event without a terminal completion/block event. Wait for evidence. `process list` is not authoritative for cron agent runs because those runs may not appear as terminal background processes.

## Cadence pitfall

Do not restore the sleep-mode default `every 30m` over an established user cadence. Pause/resume/update must preserve the explicit 10–15 minute agreement unless the user changes it.

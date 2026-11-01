# Audit recipe: forged proof and stale lease defenses

## Minimal attack matrix

| Case | Setup | Expected result |
|---|---|---|
| Raw dependency IDs | Call runtime adapter with a list/set that claims prerequisites completed | Reject; only scheduler-issued proof is accepted |
| Constructed proof | Instantiate the proof class directly, even with internal/sentinel fields | Reject unless durable task, attempt, and lease match |
| Missing durable task | Supply matching-looking run/task/dependency metadata for a nonexistent task | Reject |
| Zero-dependency replay | Claim a real zero-dependency task, then construct a proof with the wrong lease token | Reject |
| Stale attempt | Requeue/reclaim task and replay the prior attempt's proof | Reject |
| Normal path | Scheduler claims task and passes its current proof directly to runtime | Execute successfully |

## SQL facts to verify at execution

Query the durable task row by `(task_id, run_id)` and assert:

- `status` is the active claimed state;
- `lease_token` / attempt token equals the proof and task snapshot token;
- `lease_expires_at > now`;
- all dependency IDs are in the same run and terminal-success.

Use a current durable database in the negative tests. An object-only test cannot prove that lease replay is prevented.

## Frozen release sequence

1. Test each attack case RED→GREEN.
2. Run normal scheduler-to-runtime integration test.
3. Run complete relevant suite and packaging/runtime smoke gates.
4. Stage only intended files and record `git write-tree`.
5. Review that tree with the attack matrix.
6. If the reviewer finds a bypass, do not amend/commit it: make a new RED test, fix, restage, generate a new tree, and review again.
7. Commit, push, and evaluate CI only for the exact resulting commit SHA.

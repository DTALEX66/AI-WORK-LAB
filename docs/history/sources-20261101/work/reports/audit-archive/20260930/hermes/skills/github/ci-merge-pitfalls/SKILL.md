---
name: ci-merge-pitfalls
description: Unblock PR merge after force-push; fix stale CI checks.
---

# CI Merge Pitfalls (stale checks, force-push artifacts, order flakes)

Three non-obvious failures that masquerade as product bugs but are CI/merge-
machinery artifacts. Diagnose before touching code; never bypass a required-
checks rule to make them disappear. (WORK-LAB context: strict ruleset
`main-exact-sha-aggregate` requires one `aggregate` context; `gate-plan`
discovers changed paths from `BEFORE_SHA`.)

## 1. Stale failed check-run on a strict required-checks ruleset

A GitHub ruleset with `required_status_checks` (e.g. one `aggregate` context,
`strict_required_status_checks_policy=true`) binds check-runs permanently to
the run that made them. If the SAME head SHA produced one `failure` and one
`success` for the required context (a flake, a rerun, a re-trigger), the PR
`mergeStateStatus` can stay **BLOCKED** because the stale failed run still
counts — the newer success does NOT override it.

- Settle by completion-time: `gh api repos/<r>/commits/<sha>/check-runs`,
  then last-wins per context. If the last-wins required context is green but
  the rollup is still BLOCKED, that is this artifact.
- **Never** `--admin` / force-push around a required-status rule to clear it
  (a security-control bypass is itself the red flag C3/audit looks for).
- Fix: advance the head with ONE REAL commit so the new SHA carries no failed
  check-run for the required context, then merge. The old SHA's red runs are
  moot because the strict check evaluates at the actual merge head.
- A "no-op / bookkeeping" commit on a digest-scoped repo that does NOT touch
  any digest source is safe: `reports/**` and most `scripts/**` are outside
  `CANONICAL_FILES`/`SUPPORT_AREAS`, so the projection stays FRESHNESS_PASS.

## 2. Force-push orphans `BEFORE_SHA`, breaking change discovery

After rebase + `push --force` on a short-lived branch, the NEXT push-event's
`BEFORE_SHA` points at the just-replaced object, which is no longer reachable
in the runner's fetch graph. A gate-plan "Discover changed paths" step doing
`git diff --name-only "$BEFORE_SHA" "$HEAD_SHA"` then dies with
`fatal: bad object <sha>` (exit 128) → the whole job reds, downstream jobs
skip, and the aggregate gate cascades red. This is an ENVIRONMENTAL artifact,
not a code defect.

- Confirm: read the failed job log's `BEFORE_SHA` env and check that object
  no longer resolves on the remote.
- Fix: add one more real commit and a NORMAL (non-force) push so the new
  event's `BEFORE_SHA` resolves to a reachable object. Do NOT delete evidence
  or force-push again to "fix" it.
- Consequence: any head-LOCKED CI poller/watcher goes stale after a
  force-push. Kill it and start a head-TRACKING one (re-reads the branch head
  each frame), or it will report GATE_RED on the abandoned head forever.

## 3. "Red once, green again" on one SHA = an order flake, fix the contract

When a test is red on a commit and green on the re-run of the SAME commit, it
is a nondeterminism, not permission to rerun-pray. Find the contract:
- Classic shape: a parallel batch builds a summary list from
  `concurrent.futures.as_completed` (completion order, nondeterministic)
  while the contract/tests expect input order. E.g. WORK-LAB
  `services/execution-federation/parallel_dispatch.py` `parallel_dispatch_of`
  derived `succeeded`/`failed`/`notes` from the `as_completed`-filled dict.
- Fix the RIGHT layer: drive the summary from the input order (use the
  completed-dict only for lookups); `as_completed` still runs the work in
  parallel but must not set summary order. Add a regression negative control
  where a deliberately SLOW spec finishes LAST and still reports in input
  order, and verify determinism by running the suite N times (all green =
  root-fixed, not green-once).

## Merge closure reminder (ERR-089)

Pre-check `mergeStateStatus=CLEAN` (rollup, not a single run) → squash
`gh pr merge <n> --squash` → `git fetch origin main` + ff local → `local main
== origin/main` (double-sided consistent) → delete short-lived branches.
Then the POST-MERGE gate on the new main SHA is the final evidence; a
merge-queue of two PRs can land D first then C: after each merge, rebase
any pending branch onto the advanced main (disjoint file sets → clean),
force-push it, and expect one transient BEFORE_SHA red (Pitfall 2) on the
first run of the new head — clear it with the bookkeeping head-advance
(Pitfall 1) before the final merge.
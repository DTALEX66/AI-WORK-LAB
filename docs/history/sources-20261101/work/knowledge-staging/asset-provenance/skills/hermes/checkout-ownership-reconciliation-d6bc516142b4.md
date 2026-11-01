---
name: checkout-ownership-reconciliation
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/checkout-ownership-reconciliation/SKILL.md
---

---
name: checkout-ownership-reconciliation
description: "Use when resuming durable work in a dirty Git checkout."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [git, single-writer, dirty-worktree, autonomous, recovery, safety]
    related_skills: [sleep-mode, agent-workflow-fortress, project-data-boundary]
---

# Checkout Ownership Reconciliation

Use this class-level procedure whenever an autonomous loop, cron cycle, handoff, or resumed agent sees a dirty checkout or a recorded controlled-WIP list.

## Procedure

1. Capture repository root, branch, `git rev-parse HEAD`, `git write-tree`, and `git status --short` before any test or edit.
2. Compare the exact live path set against the recorded owner/controlled-WIP set. Classify every path as controlled WIP, committed HEAD, or unknown/concurrent WIP. Independently verify the checkout before trusting a persisted `blocked` state: `git rev-parse --git-dir`, `git rev-parse HEAD`, `git status --short --branch`, conflict paths, and `git write-tree` are the current authority.
3. Treat any unlisted `UU`, `AA`, modified, deleted, renamed, or untracked path as an ownership blocker. However, if live status is clean and the recorded mismatch is absent, classify the old blocker as stale/path-resolution drift, append a redacted reconciliation event, and resume only the next bounded task after recapturing identity; never propagate the stale blocker merely because `state.json` says `blocked`. In that correction case, update the durable state to `active` while preserving the scheduled job/task, current HEAD/tree, and a precise `last_evidence` entry; do not mark a task complete merely because the blocker was stale. Do not test, stage, edit, restore, reset, clean, or adopt it by merely adding it to the ledger.
4. Preserve the checkout and write a redacted state/activity event containing the mismatch and current Git identity. Set the durable loop to `blocked` or `paused` according to its contract, retaining scheduled continuation when policy requires it.
5. Resume only after an authoritative handoff or a new clean/explicitly owned checkout proves writer ownership. Re-capture branch, HEAD, tree, and status after ownership changes; old test results do not transfer across tree drift.

For canonical taskpacks that intentionally start on a dirty predecessor tree, follow `references/authoritative-taskpack-execution.md`: reconcile stale preserved task lists, classify dirty paths, build a stable candidate tree with a temporary index, and separate the tracked graph from ignored ledger state.

## Cloud-as-source-of-truth cross-analysis and residue pruning

When the user says "以云端为主 / 交叉分析 / 本地没用的可以去掉" or "云端有更新，拉取
到本地", the remote `main` is authoritative and the correct job is to (1) sync
local to remote, then (2) cross-analyze local residue and prune what the cloud
no longer needs — NOT to keep every local artifact.

Sequence:

1. `git fetch origin --prune`, then align local to remote: `git checkout main &&
   git reset --hard origin/main` only when the local tree has no owned WIP (the
   tracked `observer_runtime.py`-style edits must be re-applied, never silently
   dropped — check `git status --short` first and re-stage any real source fix).
2. `git status --short` after sync: the ONLY surviving entries should be genuine
   local residue. An authoritative cloud handoff (e.g.
   `50-taskpacks/WORK-LAB-OBSERVER-VISUAL-ASSETS-R2-STATUS.md`) supersedes any
   local simplified handoff; delete the local redundant doc if the cloud carries
   the same or better content and the local one never entered git.
3. `git branch -vv` + `git ls-remote --heads origin` to find local branches whose
   remote is already deleted (merged-PR cleanup). Each such branch is pure local
   residue → `git branch -D <b>`. Confirm remote deletion per branch with
   `git ls-remote --heads origin <b>` (empty = safe to delete local).
4. Remove git garbage from deleted branches: `git prune`.
5. Re-readback: `git rev-parse HEAD` must equal `git ls-remote origin main`
   (`awk '{print $1}'`), and `git status --short` must be empty. Report local==remote.
6. Preserve genuine local delivery that the cloud cannot reproduce, even if it is
   git-ignored (e.g. a built portable `app.exe` under `target/`). Cloud may record
   "PENDING_TOOLCHAIN_BUILD" while the local machine already has a working binary —
   that local artifact is value, not residue; keep it, don't delete it.

This "prune local residue to the cloud's shape" pass is a recurring maintenance
step, not a one-off. Keep the deletion list explicit so nothing valuable (built
artifacts, historical audit docs) is swept away.

## Remote update suitability (read-only first)

When cloud/main has advanced and the user asks whether it is suitable locally, treat the remote as a candidate tree, not an instruction to pull:

1. Run `git fetch origin --prune`, then capture status, local HEAD, `origin/main`, and `git rev-list --left-right --count HEAD...origin/main`. Never overwrite a dirty or ownership-uncertain checkout.
2. Inspect the merged PR/commit and exact-SHA required checks. Record workflow name, run attempt, job conclusions, and URLs. Green CI proves the remote tree for that SHA; it does not prove that the local Hermes/Codex live profile is synchronized.
3. Review `git diff HEAD..origin/main --name-status` and the full diff, giving extra scrutiny to config, hooks, providers, dependencies, sync/deployment code, generated files, and security rules. Classify repository-code suitability separately from live-environment suitability.
4. Validate the remote tree in a detached worktree. On Windows use a short path to avoid path-length false failures and pre-create project-owned `.hermes/task-runtime/{tmp,cache,logs}` and `.hermes/task-artifacts` before raw tests. Run the canonical quality gate and full tests; distinguish missing runtime initialization from actual source failures.
5. For provenance checks, pass an explicit manifest and native Windows live-root path, e.g. `--manifest config/skill-provenance.yaml --live-root 'C:/Users/<user>/AppData/Local/hermes'`. Do not pass Git Bash `/c/...` paths to Python `Path` code: they can resolve as `D:\\c\\...`.
6. If live SHA drift or hook trust drift appears, report the repository update as potentially suitable but stop before live sync or trust re-approval. Changing Hermes/Codex home state requires explicit approval; a manifest update alone is not live evidence.
7. Only after this audit choose fast-forward, merge, cherry-pick, or no-op. Preserve local WIP and never silently replace it. See `references/remote-update-audit.md` for the compact evidence checklist.

### Controlled staged-WIP forward-port to advanced main

When an explicitly owned staged candidate must be carried from an old base to a remote `main` that advanced while it was under review:

1. Keep the original dirty checkout untouched. Record its staged path list, `git diff --cached --check`, index tree, and a SHA-256 of a binary patch exported to a project-ignored artifact path.
2. Create a **new** worktree and feature branch from the verified `origin/main` SHA. Apply the artifact with `git apply --3way --index`; do not merge the obsolete branch or copy its whole history.
3. If a conflict is limited to a concurrently changed document, inspect all sides and compose the smallest non-duplicated result. Do not let the old candidate overwrite newly merged base text.
4. Verify the new worktree has only the approved staged paths and no unstaged source changes. Its `git write-tree` is a new identity: all earlier frozen-tree reviews and test evidence are invalid, even if the code portion is unchanged.
5. Run fresh isolated gates and obtain a new read-only review before committing. Keep test runtimes, build targets, virtual environments, and any temporary runtime link inside ignored project-local paths; never repair a clean candidate by touching the original WIP checkout.

## Managed updater autostash recovery

If a managed installer created an autostash and reset to a rewritten/diverged upstream, do not immediately `stash apply` and do not keep permanent recovery branches in the live install. Capture updater logs/reflog and stash parents, validate the candidate remote exact tree in a detached worktree, then temporarily anchor the pre-update HEAD and stash commit. Export only the user delta (`stash WIP` versus its first parent) to the owning project's ignored recovery artifacts, secret-scan and hash it, and run `git apply --check` from a detached worktree at that original parent. Only after recoverability and upstream tests pass may an authorized repair align the managed branch to `origin/main`; then remove the temporary stash/branches/worktree and require one canonical branch, zero stash, clean status and unchanged live user-state fingerprints.

Always run detached-worktree tests from the detached worktree root and clean up in a trap/finally path. See `references/managed-install-autostash-recovery.md` for the complete sequence and reset exception boundary.

## Generated-artifact drift detection via isolated rebuild

When a repository commits build outputs (bundles, `game.js`, `styles.css`, generated assets) alongside source, and you suspect the committed bundle is stale or missing fixes that exist in source:

1. **Verify in an isolated worktree, never the live checkout.** `git worktree add .hermes/task-runtime/<name> <HEAD>` puts a detached copy under the Git-ignored runtime dir; run the build there so the working tree is not polluted. Caveat on Windows: the *main* checkout can still show a tracked bundle as modified if an earlier `npm test`/build in the main tree regenerated it — confirm which tree changed before attributing cause.
2. **Establish a drift baseline.** Record `git rev-parse HEAD:<path>` for every committed bundle, then rebuild from source in the worktree and `git hash-object` the fresh output. A SHA mismatch is drift.
3. **Classify severity from the diff, not just the mismatch.** Diff the committed blob (`git show HEAD:<path>`) against the rebuilt file. A rebuilt bundle that ADDS security guards the committed one lacks (e.g. `SENSITIVE_KEYS` rejection, analytics schema version, production transport validation) is a P0: committed exports expose risk while source is already fixed but was never rebuilt-and-committed. This is exactly the "321 tests pass ≠ committed export is safe/latest/reproducible" trap — the source tests pass, but the shipped bundle predates the fix.
4. **Fix by rebuilding + committing, then prove determinism.** Rebuild through the repo's official entry (e.g. `node scripts/prepare-android-webview.mjs`), confirm the guard is now present in the tracked file, and commit. Add a deterministic drift gate (a script comparing tracked blobs to rebuilt output, with a `--check` no-rebuild mode) so a subsequent rebuild leaves `git status` clean. **Acceptance:** after a full rebuild `git diff` is empty and the gate exits 0 — same input ⇒ same output, no stale-bundle release.
5. When a tracked generated file is also matched by a `.gitignore` rule, `git add` still works (tracked files ignore ignore-rules) but needs `-f` because of the ignore rule — and that rule-vs-committed-artifact conflict itself signals a governance debt to fix under asset/volume cleanup.

See `references/remote-local-audit.md` for the paired cloud-readback checklist and the `agent-workflow-fortress` skill's taskpack reference for the fuller inheritance-matrix/net-gap execution context.
See `references/gh-missing-credential-manager-rest.md` for driving GitHub REST (PR create/merge, branch delete, rate-limit checks) via `git credential fill` when `gh` is missing but git push works through the OS credential manager (validated 2026-08-13).

### Committed build-generated media dedup (derived platform dirs)

When a game/runtime repo commits the SAME media files into multiple platform
export dirs (`android-minigame/visual`, `wechat-minigame/visual`,
`douyin-minigame/visual`, webview `assets/...`) while a build script
(`build.js` `syncAssetDirectory`) already regenerates each from canonical
sources (`assets/minigame-audio`, `games/.../abnormal_elevator_visual_assets`):

1. **Quantify first with content hashes, not size guesses.** Hash every tracked
   media file (`git show HEAD:<path>` → sha256) and group by hash; count
   duplicate groups and summed waste. This reproduces the audit figure exactly
   (e.g. 90 groups / 106 MB) so the fix target (≥80% reduction) is measurable.
2. **Confirm the derived dirs are truly regenerable.** The build script's
   `syncAssetDirectory(canonicalSource, outputDir)` proves each platform copy is
   a pure build artifact — that is the license to untrack it.
3. **`git rm -r --cached <derived-dirs>`** (keeps files on disk) — NOT a
   destructive delete. `--cached` untracks without removing the working tree.
4. **Extend `.gitignore`** for every sibling platform dir the existing rules
   miss (e.g. rules covered `android-minigame/` but not `wechat-minigame/audio`
   or `douyin-minigame/visual`). The gap is the classic
   *tracked-file-bypasses-ignore* trap: an ignore rule does not untrack an
   already-committed file.
5. **Rebuild all platforms + prepare**, then assert derived files reappear on
   disk AND the drift gate still passes (`git ls-files <dir>` = 0, `git status`
   clean after rebuild). Regeneration must be proven, not assumed.
6. **Commit the untracks + ignore additions** as one refactor. Tracked media
   count drops sharply (e.g. 363 → 113); duplicate waste → ~0.

Pitfall: `git status` showing `D` (deleted) entries after `--cached` is normal —
that is the staged untrack. Do not confuse it with real file deletion; the
files stay on disk and regenerate on build.


- A clean index does not prove a clean worktree; inspect staged and unstaged status.
- `UU`/`AA` entries require special care; never overwrite either side without explicit authorization.
- Runtime state files may preserve the blocker, but unknown source WIP must remain untouched.
- Exact-SHA CI evidence and live provenance evidence are separate gates; one cannot substitute for the other.
- For a frozen uncommitted-tree review, record branch, `HEAD`, and `git status --short`, then compute the user-specified binary-diff digest (normally `git diff --binary | sha256sum`) **before reading code**. Re-capture the same evidence after review, because any drift invalidates the original working-tree identity. If a concurrent writer commits the exact patch during review, do not silently treat an empty final worktree diff as proof the patch disappeared: compare the original base to the new `HEAD` over the reviewed path set and hash that binary diff. Only when this digest exactly matches the captured digest may findings be re-anchored to the new commit; report the ownership transition and commit SHA explicitly. Any content mismatch remains a hard stop.
- If the review contract forbids writes, do not run tests or other commands that may create bytecode, caches, temporary artifacts, or runtime state. Limit verification to static/read-only checks explicitly inside the authorized repository boundary.
- A provenance sentinel such as `pending-live-sync` is an intentional absence of live evidence, not a live hash. Do not treat a source-only provenance check as proof of a live profile.

### Deployment/configuration boundary checks for frozen reviews

When a frozen review covers a repo-to-live synchronizer, trace each sensitive configuration or state file through the **entire** operation graph: declared inventory, backup selection, staging construction, promotion/replace list, dry-run behavior, rollback, and cleanup. Excluding a file only from final `os.replace` is insufficient: copying a mixed-ownership config into staging can expose provider/auth/MCP/plugin state, and ignored cleanup failures can retain that copy.

An isolated verifier may construct a portable config only after it proves both conditions in code: (1) its Home is newly created or explicitly empty, and (2) its Home is confined to a verifier-owned temporary/project-runtime root (or was created by the verifier itself). A caller-supplied arbitrary empty directory is not, by itself, isolation. Do not rely on variable names or documentation claims as enforcement.

For declarative root-file mappings, verify a closed allowlist and prove the same normalized mapping set is used by schema loading, backup, staging, promotion, and isolated verification. For Windows post-publication rollback, require tests to assert both a non-zero result and the physical removal (or explicit retained-object failure marker) of the public target; a return-code-only test is not cleanup proof.

## Autonomous-run execution style (YOLO mode + reporting cadence)

This user runs long V4-style taskpack pushes under YOLO mode with an explicit
reporting preference. Two durable preferences govern how to behave in those
sessions:

### YOLO-mode with boundaries
When the user says “开启YOLO模式 / YOLO / 注意执行边界”, treat it as **permission
to autonomously push local staging, edits, tests, and commits without asking
per step — NOT as permission to lift the safety floor.** Keep these invariants
hard in YOLO mode:

- Hard-forbidden regardless of YOLO: `E:` drive access, credential/auth reads,
  project-external writes, `git reset --hard`, wide `git clean`, history
  rewrite, and substituting synthetic/static output for real E3/E4/E5 evidence.
- Single writer per checkout; leave sibling project checkouts untouched.
- Evidence-level honesty does not relax in YOLO: still mark E1/E2 as such and
  never claim E3/E4/E5 without the real runtime/release/commercial evidence.
- High-risk remote actions stay individually flagged even in YOLO: merge to
  `main`, tag, release, remote branch deletion are surfaced for explicit
  approval rather than run silently. Push to a feature/work branch is fine.
- A genuine runtime blocker (e.g. a daemon native module ABI mismatch under the
  system Node) is recorded as `BLOCKED` with root cause, not faked as the
  E-level evidence the task requires.

### Reporting cadence for long autonomous runs
When the user says “不要实时汇报/事事汇报，只做阶段性汇报，最后补一份摘要”:

- Do NOT narrate every tool call, command, or intermediate file write.
- Give **phase/checkpoint reports** only — a compact status table or a few
  lines after each coherent unit closes (Phase/Gate pass, multi-commit
  milestone).
- Always finish with **one consolidated final summary**: completed-by-task-ID,
  verification evidence, blockers + root cause, Git state
  (branch/HEAD/clean), and the precise next step / approval needed.
- Keep pushing work continuously; only the *reporting* is compressed. Do not
  stop working merely to report. Track progress in the todo list, checkpoint
  rarely, land one rich summary at the end.

## Live state reconciliation

When resuming a durable queue, compare persisted branch/HEAD/tree, controlled WIP, and active task against live Git before selecting a writer task. A stale state file is historical evidence, not checkout identity. If the checkout is clean, record a bounded reconciliation event and update the durable baseline to the live branch/HEAD/tree; if dirty paths are not explicitly owned, preserve them and stop before writing. For append-only activity ledgers, use a small project-local append script through the data-boundary wrapper; never rewrite JSONL with a whole-file writer.

## Session scoping across repos (user-directed single-writer focus)

When the user assigns a session to ONE repo and says to keep another repo
single-writer (e.g. "本会话专注 <repo-B>，<repo-A> 工作树保持单 writer；如需它在
<repo-A> 继续做事，两个会话先约定分工"), treat that as a hard scope boundary:

- **Do not open, read, audit, or operate on the OTHER repo in this session** unless
  the user explicitly says so. Even read-only checkouts or "just confirming state"
  in the sibling repo drift the focus and draw a correction ("不要再打扰 <repo>,
  你只负责本项目该负责的").
- If a cross-repo decision genuinely needs the sibling repo's state, do NOT go look
  — surface the dependency and ask the user to either (a) assign it to the sibling
  session, or (b) authorize this session to cross the boundary. Never resolve it by
  silently acting in both repos.
- When you find the sibling repo has been advanced by another writer (new taskpack
  version, merged PR) while you were focused elsewhere, report it as a fact and ask
  how to proceed (re-align / cherry-pick deltas / leave it) — do not start working
  in that repo to "help" it.
- Stay in the assigned repo's module roots; leave the sibling project's checkout
  untouched (reinforces the single-writer invariant).

This is a discipline rule, not a technical one: the technical conflict recovery is
below, but the preferred outcome is to never create the conflict by honoring scope.

## Parallel-session checkout conflict (sibling agent on the same tree)

A second Hermes/Codex session operating the SAME checkout can, mid-run: reset your
feature branch to an old base, `git checkout` a different branch under you, commit
opposite-direction work, and even merge a contradictory PR into `main` — all while
your worktree edits still "exist" locally. This is NOT ordinary dirty-checkout
drift; branch pointers and HEAD become unreliable moment to moment.

### Detection signals
- `git reflog -15 --date=iso` shows resets/checkouts/commits you did not issue
  interleaved with yours (timestamps + "reset: moving to <sha>" entries are the tell).
- Your feature branch suddenly points at a different commit (`git branch -v`), or a
  branch you pushed is now `behind origin/<branch>` with no action from you.
- A patch/write tool warns *"was modified by sibling subagent '<id>' ... after this
  agent's last read"* — that is an ACTIVE file race, not a benign notice.
- A PR you did not open appears merged into `main` (reflog + `gh pr view`).

### Identify the sibling session (who is writing?)

The sibling id in the patch warning is a Hermes session id
(`YYYYMMDD_HHMMSS_<hex>`). Resolve it to a real session instead of guessing:

1. `session_search(query="<id>")` or `session_search(session_id="<id>")` shows
   the session's title/source — e.g. `20260807_213755_4c151a` resolved to
   "设计增强8.7", a user desktop session (source=desktop, profile=default).
2. Or read Hermes' session DB directly (read-only):
   ```python
   import sqlite3
   c = sqlite3.connect('file:C:/Users/<user>/AppData/Local/hermes/state.db?mode=ro', uri=True)
   print(c.execute("SELECT id, source, profile_name, title FROM sessions WHERE id LIKE '2026080%' ORDER BY started_at DESC LIMIT 30").fetchall())
   ```
   (adjust the LIKE prefix to the sibling's date prefix; `source` tells you
   desktop vs subagent vs gateway platform).
3. Cross-check the live process table for the owning app: Hermes desktop
   (`hermes.exe` / Electron `Hermes.exe`), `hermes_cli.main serve` (gateway),
   or a Codex CLI. A `desktop`-source session is another window/tab of the SAME
   Hermes desktop app — usually the user simply left a long session running
   (validated 2026-08-11: the "parallel" writer was the user's own second
   desktop tab, not a rogue process).
4. Report the resolved identity to the user (session link + title + source) and
   recommend single-writer discipline across sessions; if it is the user's own
   other desktop tab, stopping it or moving it to its own repo ends the race.

### Recovery sequence (validated 2026-08-11, WORK-LAB parallel-session conflict)
1. **Freeze and audit first**: `git reflog -15 --date=iso` to reconstruct whose
   operations happened when; `git branch --show-current` + `git rev-parse HEAD` to
   learn where you actually are. Do not trust the branch name in your plan.
2. **Prove your commits survive**: `git cat-file -t <your-sha>` for every commit you
   pushed — if the object exists, your work is recoverable even if local branch
   pointers were moved or deleted. `origin/<branch>` is the safe copy.
3. **Restore your branch from the remote copy**: `git checkout -B <branch>
   origin/<branch>`. This re-points the branch and rewrites the worktree to your
   content without `reset --hard` (objects stay in reflog; the remote ref is intact).
4. **Verify absence of the opposing commit's content field-by-field** before
   trusting the restored tree: grep for the opposing commit's DISTINCTIVE markers
   (`grep -c 'scope_note\|design_config' config-ownership.json` → expect 0), not
   just its commit message. Presence of your markers (e.g. `global_configuration`,
   a rule name) is the positive check.
5. **Rebuild the intended chain on a fresh branch**: `git checkout -b <new> 
   origin/main`, then `git cherry-pick <your-sha-1> <your-sha-2> <your-sha-3>` (they
   apply cleanly when your chain forked from a point at or before the opposing merge).
   Then re-apply any worktree-only edits as a 4th commit; regenerate generated state
   (e.g. CURRENT_STATE) LAST so its digest matches the final tree.
6. **Replace the PR**: open a new PR from the fresh branch whose description states
   it supersedes the opposing PR; `gh pr close <old> --comment "Superseded by #<new>"`.
   The diff vs `main` then reads as "remove opposing changes + add correct ones".
7. **Surface the direction conflict to the user**: two sessions produced opposite
   semantics on the same contract — do NOT silently pick. Present a side-by-side
   table (your direction vs theirs per field) and ask via `clarify` which is
   authoritative BEFORE merging anything.

### Continued conflict: the sibling keeps writing (same session, later phase)

The 2026-08-11 WORK-LAB conflict did NOT stop after the first recovery. The
sibling session kept operating on the same checkout for the whole session:
re-merged `main` INTO the feature branch twice (`411b10f`, `74c13b3`), added its
own commits (`28ba0ef`) with the CORRECT direction, overwrote AGENTS.md, and
reverted a wrapper patch. Lessons from the continued phase:

- **Stage your critical edits immediately.** Staged changes (`git add` → first
  column `M ` in `git status --porcelain`) SURVIVED the sibling's branch
  switches; unstaged worktree edits were silently lost when it checked out
  another branch under you. Stage early and often; re-grep your markers after
  any checkout.
- **The sibling can merge `main` INTO your branch**, dragging the opposing
  commit's content back in through the merge. Verify field markers after EVERY
  git operation, not just once — the opposing fields reappeared post-merge and
  needed a cleanup commit removing them again.
- **The sibling can also commit the CORRECT direction** (`28ba0ef`). Never
  assume every sibling commit is wrong; grep the distinctive markers
  field-by-field and judge content, not authorship or branch.
- **Verify `git branch --show-current` immediately before `git commit`** in a
  contested checkout — a commit landed on local `main` instead of the feature
  branch (`5c20b32`). It was not pushed, so recovery was `git branch -f main
  origin/main` (from another branch — pointer sync without `reset --hard` and
  without checking out) + re-committing the same content on the correct branch.
- **Reconstruct lost worktree-only patches from conversation context**, not
  from git: a patch reverted by the sibling's checkout is gone from the
  worktree, but the full patch text still lives in your context — re-apply it
  verbatim, verify, then immediately stage.
- **Cleanest "revert" of a squash-merged opposing PR**: build the new branch
  from the pre-merge parent (`git checkout -b <new> origin/<pre-merge-sha>`)
  and cherry-pick your chain — the PR diff then reads as "remove opposing
  changes + add correct ones". Plain `git revert <squash-sha>` also works for a
  single-parent squash commit, but parent-rebase is cleaner when you are adding
  your own chain anyway.
- When the sibling eventually converges on your direction (merge titled "revert
  wins"), keep going — verify content, fix residue, and land it; do not
  re-litigate the direction.

### Pitfalls
- Branch pointers are NOT evidence of content under concurrent sessions; re-verify
  `git branch --show-current` + HEAD after every git operation in a contested checkout.
- A clean `git status` after the sibling's checkout means you are looking at THEIR
  tree, not yours — `git cat-file -t` your SHAs before concluding work was lost.
- Do not fight in-place: once a sibling session is detected, move your remaining work
  to a fresh branch/worktree from `origin/main`; in-place patching keeps losing to
  their checkouts.
- Sibling-file races: when the write tool warns about a sibling subagent, re-read the
  file immediately before patching and re-grep your distinctive markers after.

See `references/parallel-session-conflict-recovery.md` for the annotated transcript
and command chain.
See `references/open-design-two-tier-ownership.md` for the AUTHORITATIVE direction
of the WORK-LAB / Open Design ownership boundary (WORK-LAB MANAGES non-design global
config; design capability belongs to OPEN-DESIGN-Assistance). Use its marker greps
to verify which direction a contested tree actually encodes.

### Benign concurrent agent in the same checkout (bounded feature task)

A sibling subagent may be committing/creating files in the SAME repo while you
complete an ordinary bounded feature — no branch fights, just parallel writes.
Observed 2026-08-14 in ArcheAxis-Knowledge-OS: `git status --porcelain` showed
`app/main.py` / `app/capability/store.py` modified and several new untracked
files (`app/setup/`, `app/workspace/migrate.py`, new tests) appear MID-task;
none were mine. Handling pattern:

1. **Baseline at start, re-check before staging.** Capture
   `git status --porcelain` when the task begins; re-run it right before
   `git add`. Any path that is new since baseline and not created by you is a
   concurrent agent's in-flight work — never fix, revert, review, or stage it.
2. **Attribute repo-wide lint failures by file ownership.** `ruff check .`
   failing on files you never touched (F821/I001 in a sibling's mid-edit
   `app/setup/`, `app/workspace/migrate.py`, etc.) is the sibling's debt, not
   yours. Verify via git status that those files are foreign, scope your
   evidence to `ruff check <your-files>`, and report the repo-wide failures as
   pre-existing/foreign in the final summary rather than silently fixing
   someone else's half-written code.
3. **Stage by explicit path only.** `git add <your-file-list>` then confirm the
   staged set in `git status --porcelain` matches exactly your files; leave
   foreign `??`/`M` entries unstaged.
4. **Re-run your test suite at the end.** The sibling may edit shared modules
   (e.g. `app/main.py`) mid-task; the final green run must postdate their last
   visible change so your evidence is not invalidated by tree drift.

### Supersession by a newer taskpack (sibling redid your work at a higher version)

The hardest variant of the parallel-session conflict is when the sibling does NOT
revert or contradict you — it **re-implements your divergent work under a NEWER
authoritative taskpack and merges it to `main` first** (e.g. your v4.1 Wave C0
gets redone by the sibling as V4.2 "Phase 1 P0 truth fixes" with a different
implementation). Your branch then forks from old history and is NOT needed.

Detection (before you decide to merge/cherry-pick anything):
1. `git fetch origin` then `git rev-list --left-right --count HEAD...origin/main` —
   a fork (non-zero on both sides) means cloud moved under you.
2. `git log --oneline main..origin/main` — read the NEW commit subjects. If they
   name a newer taskpack (`V4.2`, `V42-0201..0408`) whose titles shadow your
   work (`plan-only config`, `fail-closed CI`, `evidence-gated adapters`,
   `MiniGame frozen boundary`), it is a supersession, not a competing edit.
3. Prove overlap with `git show <new-sha> --stat` vs the files your divergent
   branch touches (`git show --stat <your-sha>`). Shared files with same intent =
   re-implementation; do not double-land.

Recovery (align to the new authority, keep only true deltas):
1. **Do not merge or rebase your stale branch** — it conflicts pointlessly and
   the new taskpack already covers the intent. Align local `main` to the new
   authority: `git checkout main && git merge --ff-only origin/main`
   (fast-forward only; if it refuses, the local main was itself dirtied — see
   sibling handling above).
2. **Keep your old branch** (`git branch <old>`, do not delete) so you can
   harvest genuinely-unique artifacts the new taskpack lacks — e.g. your
   `SPDX` backfill / `SBOM` / `capability-evidence-index` may exist in your fork
   but NOT in the merged V4.2 `config/`. `git ls-tree origin/main --name-only
   <dir>` + `git ls-tree -r origin/main --name-only | grep <marker>` tells you
   what the new authority already carries before you re-add anything.
3. Ask the user, per the direction-conflict rule, whether to cherry-pick those
   unique artifacts into the new taskpack or drop them — do not silently merge.
4. Record in memory/ledger the supersession fact (my taskpack vs the merged one,
   and which artifacts were/weren't carried) so a later session does not redo it.

### Protected `main`: PR + squash is the only path; SSH-push when HTTPS lacks creds

Two recurring mechanics for governed repos where `main` is protected
(`required_status_checks`, `required_linear_history`, merge commits disabled):
- **Direct push to `main` is refused** (`protected branch hook declined` /
  `remote rejected`). Do not try to bypass. Push a feature branch
  (`git push <remote> HEAD:<branch>`), open a PR, wait for the required check
  (`aggregate`), then merge with `gh pr merge <n> --squash --delete-branch`.
  Merge-commit `--merge` is refused on linear-history repos; `--squash` works.
  A transient "not mergeable / BLOCKED / UNKNOWN" right after CI is often
  GitHub recomputing after a head change — re-check `gh pr view <n> --json
  mergeStateStatus` before giving up.
- **HTTPS remote with no credential helper but `gh` authed via SSH**: `git push
  origin` fails (`could not read Username` / `git-askpass` missing). Detect with
  `gh auth status` ("Git operations protocol: ssh"). Push over SSH explicitly
  WITHOUT changing the remote: `git push git@github.com:<owner>/<repo>.git
  HEAD:<branch>`. Test auth first with `ssh -T -o ConnectTimeout=10 git@github.com`
  ("successfully authenticated").
- `-X ours` vs `-X theirs` in `git merge <branch>` are relative to the CURRENT
  branch: `-X theirs` prefers the OTHER branch, `-X ours` prefers yours. Getting
  this backwards silently merges the OPPOSING content (observed: intended
  "revert branch wins" but `-X theirs` from `main` kept `main`'s wrong text).
  Verify markers field-by-field after the merge, not just the merge message.

## Pitfalls

- **Missing local Git identity when committing a predecessor batch.** A repo with
  no configured `user.name`/`user.email` (and none globally) fails any commit with
  `fatal: unable to auto-detect email address (got '...')`. Fix by reading the
  existing history author and setting it **repo-local** to match, NOT `--global`:
  `git log -3 --format="%an <%ae>"` then `git config user.name "..."` /
  `git config user.email "..."` (for GitHub-hosted repos use the GitHub noreply
  address, e.g. `<id>+<login>@users.noreply.github.com`). Matching the history
  author keeps the handoff commit's identity consistent with prior merges.
- **Contract/schema catalog drift breaks the aggregate gate even when the code is fine.**
  When a governed repo adds new schemas/contracts (e.g. `config-ownership.schema.json`,
  `platform-identity.schema.json`) AND registers them in `contract-catalog.json`, a
  verifier that enumerates an EXPECTED set of contract ids AND a test that hardcodes
  the count (`assertIn("...PASS contracts=28 schemas=28", stdout)`) BOTH go stale
  independently. The workflow/observer jobs pass but `integration` fails on
  `catalog ids must equal [...]; got [...]`, which flips `aggregate` FAIL. Fix all
  three in one batch: (1) verifier `EXPECTED` owner dict, (2) verifier
  `CANONICAL_SCHEMA_PREFIXES` map, (3) any hardcoded `contracts=N schemas=N` string
  in the test. Grep for `contracts=` / the old count / the new contract ids across
  scripts+tests before pushing. Local `verify_contract_catalog.py` green is necessary
  but not sufficient — the hardcoded test count must also be updated.
- Do not run tests against a moving or ownership-uncertain checkout when project policy makes that evidence unsafe.
- Do not use reset, checkout, restore, clean, or force operations to make ownership appear resolved.
- Missing/absent CI on a commit is NOT automatically a failure or a skipped gate. GitHub Actions `paths:` filters trigger a workflow only when the commit touches a watched directory. A commit that only edits an unwatched tree (e.g. `minigame-runtime/**` while the workflow watches `opendesign-assistance/**`) will legitimately show no check-runs and a `pending` commit status. Before treating absent CI as a blocker, confirm with `git show <sha> --name-only` which directories the commit actually touched and compare against each workflow's `paths:` — this is a "design-intent no-op", distinct from a genuine skip/queue-fail.
- A branch-pointer lag is NOT the same as content drift. Two branches with different HEADs can still have identical trees — prove content equality with `git rev-parse A^{tree}` vs `git rev-parse B^{tree}`, not by comparing HEAD SHAs alone. Local `main` may lag `origin/main` by a commit that is already present on the working branch; `git branch --contains <sha>` resolves whether the commit is actually missing anywhere.
- **Multi-PR batch on one worktree bleeds uncommitted changes across branches (validated 2026-08-13).** Delivering one taskpack as 3 dependent PR branches in a single checkout: files edited for branch B stay modified when you `git checkout` branch A, and `git commit` on A can sweep B's files in (worse when a `.githooks` pre-commit hook auto-stages generated state like CURRENT_STATE). Before switching branches, back up the uncommitted work to the project's ignored runtime dir (`cp <file> .hermes/task-runtime/`) or `git stash -u`; restore after checkout. `git checkout` aborts when an untracked file would collide with a tracked file on the target branch — move the file out of the tree first. Use `git commit --no-verify` for surgical single-file commits when the hook auto-stages unrelated files, and inspect `git diff --cached --name-only` before every commit; recover a hook-contaminated commit with `git reset --soft HEAD~1` + re-stage only the intended files.
- **Rebase conflict in generated state resolves by regenerating, not by hand-merging (validated 2026-08-13).** When generated projections (e.g. `00-governance/generated/CURRENT_STATE.json/.md`) conflict during `git rebase origin/main`, resolve by `git checkout --theirs <generated-files>` (or pick either side), then run the repo's generator (`python scripts/ci/generate_current_state.py --root .`), `git add` the regenerated output, `git rebase --continue`. Hand-merging generated digests guarantees a stale digest that will fail `--check-current`.
- **Skill-provenance gates hash CRLF-normalized bytes, not raw file bytes (validated 2026-08-13).** After editing a tracked skill (e.g. `skills/model-switch/SKILL.md`), a provenance gate reports `source SHA drift` unless the registered `source_sha256` uses the validator's canonical form: `hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()`. Read the validator's own `sha256()` (e.g. `scripts/security/check_skill_provenance.py`) and compute with the SAME normalization — raw-bytes SHA256 on a Windows CRLF checkout produces a spurious drift that fails the gate.
- **Force-push after rebase makes the PUSH-event CI run fail spuriously (validated 2026-08-13).** `github.event.before` points at the pre-rebase SHA; after the history rewrite, `git diff "$BEFORE_SHA" "$HEAD_SHA"` in "Discover changed paths" errors, failing the push-event run. The pull_request-event run is authoritative for merge, but the stale push-run failure pollutes check-runs and can flip `mergeState` to unstable / block the merge API with "Required status check ... is failing". Distinguish by listing runs per head SHA (`.../actions/runs?head_sha=<sha>`): failed `event=push` + green `event=pull_request` = stale. Fix by pushing an empty commit (`git commit --allow-empty -m "ci: retrigger"`) so GitHub starts a fresh push run with a valid `before`.
- **CI watchers attach to a STALE run after force-push/amend (validated 2026-08-12):** `gh pr checks --watch` and `gh run watch <id>` bind to the run that exists when the watcher starts — after amending or force-pushing a branch, the watcher reports "already completed" / "no checks reported" against the OLD run while the new commit's run is still queued. Always resolve the current run first: `RUN=$(gh run list --branch <branch> --limit 1 --json databaseId --jq '.[0].databaseId')`, then poll `gh run view $RUN --json jobs` (or a `for i in $(seq 1 N); do sleep 30; ...; done` loop breaking on success/failure). A merge-state `CLEAN` combined with "no checks reported" means the branch has NO real run yet — do not merge on that alone.
- **Merging a PR whose CI never ran leaks all skipped lint debt into the next PR (validated 2026-08-12):** a PR merged with `no checks reported` (checks skipped/never started, mergeStateStatus CLEAN) ships untested. The next full-CI PR on `main` then explodes with every error the skipped gates would have caught — observed: one merge skipped lint, the following PR found 20 ruff errors (N806/E741/B904/N814) plus a convention-check failure across files from the merged PR. Before merging, confirm the branch has a real completed run (gateplan + lint + test + wheel-smoke all concluded), or budget an immediate lint-cleanup PR.
- **Canonical branch carrying commits already squash-merged upstream (validated 2026-08-12):** after a batch of PRs merge, the canonical checkout's branch can hold the SAME content under different SHAs (its commits were cherry-picked/re-created into PR branches, or it was never reset after upstream merges). Rebase then conflicts against `main` pointlessly. Detect with `git diff origin/main..HEAD --stat` — empty diff (plus clean status) means content-equivalent; `git checkout main && git reset --hard origin/main` is then safe, or `git reset --hard origin/main` on the current branch when `main` is busy on another worktree (`fatal: 'main' is already used by worktree`). For NEW work after that, `git worktree add -b <branch> origin/main` + `git cherry-pick <sha>` beats rebasing the stale canonical branch. A failed `gh pr create` with "Head sha can't be blank / No commits between main and <branch>" is the tell that the push/rebase produced an empty branch.
- A freshly-created Git worktree can show a tracked fixture as `M` with NO real content change, purely from Windows autocrlf CRLF normalization. `git diff` then looks like only line-ending noise and the repo convention checker may flag CRLF/missing-final-newline on it. Before treating that file as owned WIP: compare its content to HEAD (`git diff --word-diff`, or `git show HEAD:<path>` vs the working copy with `diff`), and if only `\r\n` vs `\n` differs, it is platform checkout noise, not a real change — do NOT commit it, exclude it from staging, use explicit-path `git add <task-files>` and verify `git diff --cached --name-status` lists exactly your task files, and record in the reconciliation event that the CRLF delta is not owned WIP. (In a prior session this made `tests/fixtures/readability_article.html` appear modified in `axw-exec` even though the working copy byte-for-byte matched its index except line endings.)
- For a complete local-vs-remote audit, combine the Git evidence (`git rev-list --left-right --count`, tree hashes, `git branch --contains`) with the cloud evidence (`gh run list --json headSha`, `gh api .../commits/{sha}/check-runs`, `gh api .../commits/{sha}/status`, `gh pr list`, `gh api repos/{owner}/{repo}/branches`). Git status alone cannot prove a commit was pushed or that CI ran. See `references/remote-local-audit.md`.

## Verification

Record final `git status --short`, HEAD/tree identity, durable state mode, and ledger append result. A precise blocker is valid evidence; never convert ownership failure into completion.

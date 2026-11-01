# Obsidian Developer Console Stabilization — 2026-06-30

Use this reference when the user pastes Obsidian Developer Console logs from the knowledge-base vault.

## Error classes and durable fixes

### Spaced Repetition: `this.list.splice is not a function`

Observed stack:

```text
plugin:obsidian-spaced-repetition ... TypeError: this.list.splice is not a function
QuestionPostponementList.clear
QuestionPostponementList.clearIfNewDay
DataManager.initOSRCore
```

Root cause: the plugin constructs `QuestionPostponementList(..., pluginData.buryList)`. If `buryList` is `false` or any non-array value, `clear()` calls `this.list.splice(0)` and crashes.

Fix `.obsidian/plugins/obsidian-spaced-repetition/data.json`:

```json
{
  "buryDate": "YYYY-MM-DD",
  "buryList": [],
  "questionPostponementList": []
}
```

`questionPostponementList` alone is not sufficient on versions that read `pluginData.buryList`.

### Tasks: repeated `Unexpected failure to create a list item from line...`

If Tasks warns on tables/headings/blank lines, reduce parser edge-cases in files it reports:

1. Convert CRLF/CR-only files to LF.
2. Add blank lines before headings after list blocks.
3. Prefer ordinary bullet lists over Markdown tables in management dashboard files that Tasks repeatedly scans.

This is usually non-fatal, but if the user is watching Developer Console, make the reported files parser-friendly rather than dismissing it.

### Omnisearch: `Cannot read properties of undefined (reading 'keys')`

Observed during cache load / vacuuming / removal of deleted paths after many files were deleted or archived.

Fix `.obsidian/plugins/omnisearch/data.json` to force a clean rebuild:

```json
{
  "useCache": false,
  "DANGER_forceSaveCache": false,
  "PDFIndexing": false,
  "officeIndexing": false,
  "imagesIndexing": false
}
```

After restart, Omnisearch may index more slowly once. If the same error persists after a clean rebuild, temporarily disable or reinstall Omnisearch.

### Obsidian Git: `No upstream-branch is set!`

If the vault is intentionally local-only with no remote, the plugin can still commit successfully, then fail during sync/push.

Fix `.obsidian/plugins/obsidian-git/data.json` for local-only auto-backup:

```json
{
  "autoSaveInterval": 30,
  "autoPushInterval": 0,
  "autoPullInterval": 0,
  "autoPullOnBoot": false,
  "pullBeforePush": false,
  "disablePush": true,
  "differentIntervalCommitAndPush": true,
  "disablePopupsForNoChanges": true
}
```

`differentIntervalCommitAndPush: true` makes auto backup commit-only instead of `commitAndSync`.

## Plugin directory hygiene

Do not leave `.bak_*` files or whole `.bak_*` plugin directories under `.obsidian/plugins/`. Obsidian can scan them or Git will keep tracking stale plugin code. Move backups to the project workspace, e.g.:

```text
D:/All projects/Obsidian-Assistance/archived-config-backups/
```

Then commit the deletion/move in the vault's local Git so the working tree is clean.

## Verification checklist

- JSON parses with UTF-8/UTF-8-SIG.
- `buryList` is an array.
- Omnisearch `useCache` is `false` for the next restart.
- Obsidian Git has `disablePush: true` and `differentIntervalCommitAndPush: true` for local-only vaults.
- Reported Markdown files use LF line endings.
- `.obsidian/plugins/` has no `*.bak_*`, `*bak_*`, or whole backup plugin directories.
- Vault local Git has a clean status after committing the config changes.

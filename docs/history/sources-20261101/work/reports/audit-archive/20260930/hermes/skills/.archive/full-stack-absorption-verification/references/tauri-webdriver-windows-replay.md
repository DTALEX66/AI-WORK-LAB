# Tauri WebView2 native WebDriver replay recipe

Use this reference when a Tauri acceptance must prove real WebView clicks rather than Computer Use/UIA.

## Prerequisites

1. Build the current worktree executable; do not reuse an old portable EXE.
2. Run the repository's real `prepare_bundle` from the same worktree and keep the destination under that worktree's `.hermes` directory.
3. Verify the WebView2 browser version from the created WebDriver session, then acquire an `msedgedriver` with the same major/full version when available. A working session with a mismatched driver is only a warning-bearing partial result.
4. Start the native driver and `tauri-driver` on isolated localhost ports. Create a session with W3C capabilities containing `tauri:options.application` pointing to the current executable.

## WebDriver protocol details

- Establish the session through `POST /session`; record `browserName`, `browserVersion`, `msedgedriverVersion`, and `sessionId`.
- Some tauri-driver/native-driver combinations reject an empty body for element click with `invalid argument: missing command parameters`. Send a JSON command body such as `{"button": 0}` for `POST /element/{id}/click` and verify the element has a non-zero `rect` first.
- Hidden nav elements commonly have `rect.height == 0`; first click the visible rail module, then locate the visible route item and click that current element reference. Never reuse stale element IDs after navigation or async refresh.
- After every action, re-read URL/source or a semantic DOM projection. Do not infer success from HTTP 200 alone.
- Use fresh DOM/element lookup after modal close, navigation, or refresh. A modal's hidden HTML can make source text appear present while the control is not actionable.

## Minimum desktop matrix

For one isolated data root, execute and record separately:

```text
current executable/session
→ real WebView intake action
→ persisted backend transition
→ Research/Knowledge action
→ Learning action/practice
→ close session
→ new WebDriver session
→ same-case semantic readback
```

Keep failure→retry→replay as a separate row. A backend replay test or Chromium result never inherits Tauri WebDriver coverage. If the UI does not naturally produce `failed`, seed only the isolated test database through the controlled SQL failure fixture after proving the success path, then use the real UI retry/dispatch actions.

## Cleanup

Delete the WebDriver session first so Tauri/Core descendants receive normal shutdown. Then stop only the native driver and tauri-driver processes owned by the run, verify their ports are closed, and do not mass-kill unrelated `msedgewebview2.exe` processes. Keep downloaded drivers, bundles, logs, and backups under the project `.hermes/task-runtime` boundary.

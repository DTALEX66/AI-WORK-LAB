# Terminal Theme Checklist

Use this checklist before applying or recommending a terminal/Hermes skin preset.

## Scope

A terminal theme is a visual preset only. It must not change:

- provider/model;
- MCP servers;
- plugins;
- tools/toolsets;
- approvals/yolo;
- Gateway credentials;
- Codex auth or sandbox mode;
- project permissions.

## Evidence before saying applied

Do not say a skin is active unless one of these is verified:

- Hermes `/skin status` or config readback shows the requested skin;
- Windows Terminal `settings.json` has the scheme and profile reference after user-approved write;
- VS Code active theme is visible/readable from the target environment;
- a screenshot/visual capture confirms the active UI.

If only a template was written, say: `template available, not applied`.

中文状态说明：模板已提供，不代表已应用；不自动改用户 settings。

## Recommended mappings

| Role | Catppuccin Mocha |
|---|---|
| background | `#1e1e2e` |
| panel | `#181825` |
| border | `#45475a` |
| text | `#cdd6f4` |
| muted | `#bac2de` |
| command/info | `#89b4fa` |
| accent/model | `#cba6f7` |
| success/verified | `#a6e3a1` |
| warning/unverified | `#f9e2af` |
| failed/danger | `#f38ba8` |
| blocked/manual action | `#fab387` |
| network/gateway | `#94e2d5` |

## Accessibility checks

- Warnings and failures must not rely on color alone; include text labels.
- Keep command output readable with monospace font and sufficient contrast.
- Avoid low-contrast gray-on-dark for evidence paths and exit codes.
- Busy/queued/blocked states need distinct words, not just spinner color.

## Manual application examples

Hermes session skin:

```text
/skin catppuccin-mocha
```

Portable config baseline, only if explicitly intended for this pack:

```yaml
display:
  skin: catppuccin-mocha
```

Windows Terminal: copy the scheme from:

```text
templates/windows-terminal/catppuccin-mocha.json
```

Then add it to the user-owned Windows Terminal `schemes` array manually. Do not overwrite the whole settings file.

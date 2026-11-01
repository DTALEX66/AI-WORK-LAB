# Open Design plugin install and smoke-test guide

This repo stores local Open Design enhancement plugins under:

```text
packages/capabilities/plugins/<plugin-name>/
  SKILL.md
  open-design.json
  README.md
```

The repo is the source of truth; do not edit copied plugin files in an app cache by hand. If Open Design requires plugins to be copied or linked into a local registry folder, copy from this repo after every change.

## Current plugin set

```text
uiux-layout-director          UI/UX, website, menu, navigation, dashboard
graphic-design-director       graphic design, posters, covers, banners, campaigns
minigame-ui-director          mobile minigame HUD/IAA screens
anomaly-monitor-hud           CCTV/HUD/surveillance/control-console interfaces
design-qa-critic              strict design review and next-prompt generation
brand-visual-director         brand identity, VI, visual design, 2D systems
spatial-exhibition-director   culture walls, exhibition halls, 2D/3D spatial design
```

## Install/recognition checklist

1. Keep this repo cloned locally:

```text
D:\All projects\DESIGN-LAB
```

2. Run the repo verifier before installing/copying:

```bash
python design-lab/scripts/verify_open_design_host_adapter.py
```

Expected:

```text
VERIFY_RESULT=OK
```

3. In Open Design, add or select the local plugin folder if the app supports workspace/plugin sources. Use:

```text
D:\All projects\DESIGN-LAB\design-lab\plugins
```

4. If Open Design only supports per-plugin folders, add these directories individually:

```text
packages/capabilities/plugins/uiux-layout-director
packages/capabilities/plugins/graphic-design-director
packages/capabilities/plugins/minigame-ui-director
packages/capabilities/plugins/anomaly-monitor-hud
packages/capabilities/plugins/design-qa-critic
packages/capabilities/plugins/brand-visual-director
packages/capabilities/plugins/spatial-exhibition-director
```

5. If Open Design requires copy-based installation, copy the whole plugin directory, not individual files. Keep these three files together:

```text
SKILL.md
open-design.json
README.md
```

## Smoke-test prompts

Use one short prompt per plugin. A pass means the generated plan mentions the relevant local template references and produces the expected output contract.

```text
Use uiux-layout-director to design a responsive pricing page for a GPT design tool.
```

```text
Use graphic-design-director to create a Xiaohongshu cover and social card for a premium AI design launch.
```

```text
Use minigame-ui-director to design the main HUD screen for a mobile anomaly monitor minigame.
```

```text
Use anomaly-monitor-hud to design a dark CCTV control console for a subway platform anomaly.
```

```text
Use design-qa-critic to review this generated landing page for AI slop, hierarchy, mobile fit, and implementation realism.
```

```text
Use brand-visual-director to create a brand identity system for an industrial AI design studio.
```

```text
Use spatial-exhibition-director to design a corporate culture wall and a 3D exhibition hall hero moment.
```

## Expected plugin behavior

A healthy plugin response should include:

```text
- clear design objective
- local template references or rules
- output contract sections from SKILL.md
- concrete Open Design generation prompt
- production/implementation constraints when relevant
```

Reject or retry if the output:

```text
- ignores the requested plugin
- behaves like a generic chatbot answer
- produces only mood words with no layout/component/material decisions
- misses the domain-specific template references
- asks for an OpenAI API key when the intended route is Codex OAuth/subscription
```

## Troubleshooting

### Plugin not visible

Check:

```bash
python design-lab/scripts/verify_open_design_host_adapter.py
```

Then confirm each plugin has:

```text
open-design.json
SKILL.md
README.md
```

And manifest fields:

```text
$schema
specVersion
name
entry = SKILL.md
od.kind = skill
od.capabilities includes prompt:inject
od.categories non-empty
od.suggestedInputs non-empty
```

### Open Design uses the wrong model or asks for an API key

For this user's setup, use the Codex CLI route, not OpenAI BYOK:

```text
Open Design → Codex CLI → CODEX_HOME / .codex OAuth → GPT subscription model
```

Run:

```bash
python design-lab/scripts/doctor_open_design_windows.py --project-root "D:\All projects\DESIGN-LAB" --strict
```

### Plugin output is too generic

Use `design-qa-critic` against the result, then regenerate with one of the templates from:

```text
design-lab/templates/INDEX.md
```

### After changing plugins or templates

Run:

```bash
python design-lab/scripts/verify_open_design_host_adapter.py
```

Commit only after it reports:

```text
VERIFY_RESULT=OK
```

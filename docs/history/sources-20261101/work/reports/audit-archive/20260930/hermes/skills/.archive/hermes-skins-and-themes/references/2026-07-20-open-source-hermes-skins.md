# 2026-07-20 Open-source Hermes skin sources

Session-specific findings for the `hermes-skins-and-themes` umbrella skill.

## Official runtime facts

- Official docs page: `https://hermes-agent.nousresearch.com/docs/user-guide/features/skins`
- Source of CLI skin engine: `hermes_cli/skin_engine.py`
- CLI/TUI user skins are YAML files under `$HERMES_HOME/skins/<name>.yaml`.
- Activation paths:
  - in-session: `/skin <name>`
  - persistent: `hermes config set display.skin <name>` followed by `/reset` or a new session.

## Live built-in CLI/TUI skins observed

- `default`
- `ares`
- `mono`
- `slate`
- `daylight`
- `warm-lightmode`
- `poseidon`
- `sisyphus`
- `charizard`

## Desktop theme distinction

Hermes Desktop has a separate theme system. Files inspected in the live Hermes source included:

- `apps/desktop/src/themes/use-skin-command.ts`
- `apps/desktop/src/themes/user-themes.ts`
- `apps/desktop/src/app/command-palette/marketplace-theme-page.tsx`
- `apps/desktop/src/themes/presets.ts`

Desktop built-ins observed:

- `nous`
- `midnight`
- `ember`
- `mono`
- `cyberpunk`
- `slate`

Desktop also has a VS Code Marketplace theme installer path. CLI YAML skins do not automatically become Desktop themes.

## Open-source repos verified as reachable

- `https://github.com/joeynyc/hermes-skins`
  - Verified remote head existed on `main`.
  - Contains many CLI YAML skins under `skins/`, including `catppuccin`, `mythos`, `nous`, `sakura`, `neonwave`, `netrunner`, etc.
- `https://github.com/novicedino-learningAI/psi-cobalt-skin`
  - Verified remote head existed on `main`.
  - Contains `psi.yaml`.
- `https://github.com/nosleepcassette/skinwalker`
  - Verified remote head existed on `main`.
  - TUI-based Hermes skin editor/manager.
- `https://github.com/cocktailpeanut/hermes-mod`
  - Verified remote head existed on `master`.
  - Visual skin editor referenced by official docs.

## Audit lesson

Do not blindly install every skin from a community repo. During review, `neonwave.yaml` contained suspicious/incorrect branding text in `welcome`/`goodbye` resembling stale tool-output instructions:

```text
File unchanged since last read...
refer to that instead of re-reading...
```

Treat this as a skip/repair candidate rather than installing unmodified. The durable lesson is: parse and scan skin YAML text before copying to live Hermes.

## Skins installed in that session

Installed to `$HERMES_HOME/skins/` after validation:

- `catppuccin.yaml`
- `mythos.yaml`
- `nous.yaml`
- `sakura.yaml`
- `psi.yaml`
- generated local `purple-gemstone.yaml`

Persistent config was set to:

```yaml
display:
  skin: purple-gemstone
```

This session-specific install state may change later; future agents should re-check live config before relying on it.

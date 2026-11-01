# Hermes Token Monitor Desktop

Windows-first Tauri 2 desktop dashboard for local token usage observability.

## What it measures

The app reads user-selected local `.json` and `.jsonl` files/directories and only counts explicit usage fields such as `input_tokens`, `output_tokens`, `prompt_tokens`, `completion_tokens`, `cached_input_tokens`, `reasoning_tokens`, and `total_tokens`.

It does not estimate tokens from text length, read credentials, call provider APIs, or upload logs.

## Role: specialist helper (U09 usage convergence)

This app is the **specialist helper** of WORK-LAB's usage observability, not a
second usage/cost engine. The single canonical token/usage/cost contract is the
JSON-Schema SSOT `packages/contracts/schemas/workflow/usage-observation.schema.json`
(the Observer's main UI reads that same canonical projection). This tool only
**counts explicit token fields** from user-selected local files and never
computes money cost (no price/FX/quota), so it cannot fork cost truth away from
the canonical contract. Retiring this specialist UI is an explicit, authorized
decision ("no deletion before parity"), not an implicit one. Conformance to the
canonical contract is machine-verified by `scripts/ci/verify_usage_convergence.py`.

## Provider display

Models and explicit provider/source labels are grouped as:

- `GPT / Codex`
- `DeepSeek`
- `Kimi`
- `Other`

The default dashboard is **本次新增**: after monitoring starts, it subtracts the initial historical snapshot and shows only usage added while the monitor is running. Use **历史累计** to inspect all recognized records in the selected sources.

## HUD view

The default surface is the **Hermes HUD**: a dark glass panel with per-provider
rings, colored bot glyphs, a top status glow, large tabular totals, 14-day
sparklines, and a selected-provider detail card. Rings encode **token share**,
not quota or remaining balance, and are labeled `份额`.

- **紧凑 / 展开** switches between a floating summary and the full HUD.
- Selecting a ring filters the detail card without changing any data.
- `—` means unknown; `0` is shown only when the value is known to be zero.
- **仪表盘** opens the original light dashboard; **HUD 视图** returns here.
- View and mode travel in the URL (`?view=hud&mode=compact`); web storage is not used.

When the app is opened in a plain browser (no Tauri runtime), it serves
deterministic sample data and never reads local files: use
`?demo=1&view=hud&mode=compact` for the compact phenotype or
`?demo=1&view=hud&empty=1` for the unknown/empty state.

The light dashboard remains available as the secondary surface (SF Pro/system
font stack, white translucent cards, quiet gray hierarchy, blue primary action).
Closing the window hides it to the Windows notification area; use the tray menu
to show it again or exit.

## Development

```powershell
npm install
npm test
npm run build
npm run tauri dev
```

The source field accepts multiple paths separated by semicolons. Use only local session or usage exports; do not select credential, OAuth, Cookie, or `.env` files.

`dist/`, `node_modules/`, `src-tauri/target/`, and generated `src-tauri/gen/` files are ignored by the repository. `package-lock.json` and `src-tauri/Cargo.lock` are source dependency locks and may be reviewed for submission.

/**
 * UI_TOKENS (20260921): single source of truth for WORK-LAB Observer theme
 * values. The CSS variable blocks in src/index.css MUST mirror these exact
 * values (asserted by tokens.test.ts). Authority: .ui-reference/WORK-LAB/
 * 10_B10 (visual supreme), L4 WORK-LAB_design_tokens.json, L7 theme/tokens.json
 * — three-way identical.
 *
 * Accent colors are RGB channel triples ("42 145 255") because index.css
 * defines them as `rgb(var(--X-rgb) / <alpha-value>)` for Tailwind alpha
 * modifiers. Surfaces are hex strings.
 */

export type ThemeAccentKey =
  | "primary"
  | "secondary"
  | "success"
  | "warning"
  | "error"
  | "info";

export interface ThemeColors {
  bg: string;
  sidebar: string;
  panel: string;
  panel2: string;
  border: string;
  ink: string;
  muted: string;
  /** hex, for reference/tests */
  primaryHex: string;
  secondaryHex: string;
  successHex: string;
  warningHex: string;
  errorHex: string;
  infoHex: string;
}

export interface ThemeValues {
  /**
   * RGB channel triples matching index.css `--X-rgb` variables exactly.
   * Keyed by accent name (primary/secondary/success/warning/error/info).
   */
  accents: Record<ThemeAccentKey, string>;
  colors: ThemeColors;
  radius: { sm: string; md: string; lg: string; xl: string };
  shadow: string;
  glassBlur: string;
  motion: {
    fast: string;
    base: string;
    modal: string;
    drawer: string;
    emphasis: string;
    pressed: string;
  };
  density: { comfortable: string; default: string; compact: string };
}

export const DARK: ThemeValues = {
  accents: {
    primary: "42 145 255",
    secondary: "32 205 225",
    success: "34 197 94",
    warning: "245 158 11",
    error: "239 68 68",
    info: "56 130 246",
  },
  colors: {
    bg: "#050D16",
    sidebar: "#07111C",
    panel: "#081420",
    panel2: "#0C1B2A",
    border: "#17435D",
    ink: "#EEF6FC",
    muted: "#8EABBC",
    primaryHex: "#2A91FF",
    secondaryHex: "#20CDE1",
    successHex: "#22C55E",
    warningHex: "#F59E0B",
    errorHex: "#EF4444",
    infoHex: "#3882F6",
  },
  // sm is the pinned skin's value: skins/b10.css declares --radius-sm:12px and loads after index.css, so
  // 12px is what every consumer renders. scripts/ci/verify_css_token_mirror.py keeps the two in step.
  radius: { sm: "12px", md: "10px", lg: "16px", xl: "22px" },
  shadow: "0 20px 80px rgba(0, 0, 0, 0.35)",
  glassBlur: "18px",
  motion: {
    fast: "120ms",
    base: "180ms",
    modal: "220ms",
    drawer: "280ms",
    emphasis: "420ms",
    pressed: "80ms",
  },
  density: { comfortable: "68px", default: "56px", compact: "44px" },
};

export const LIGHT: ThemeValues = {
  accents: {
    primary: "27 127 230",
    secondary: "14 147 165",
    success: "21 128 61",
    // index.css html.light moved this channel to 154 74 5 (#9A4A05) because amber as light text
    // measured 4.48:1; the same channel feeds the text role, so the record has to carry the readable one.
    warning: "154 74 5",
    error: "185 28 28",
    info: "29 78 216",
  },
  colors: {
    bg: "#F4F7FA",
    sidebar: "#E4EBF2",
    panel: "#FFFFFF",
    panel2: "#EAF0F6",
    border: "#D5E2EC",
    ink: "#0B1420",
    // The AA value index.css and skins/l10b-shell.css both ship for the light muted role. #5A7184 lived here
    // after that fix and still reached the DOM: TopStatusBar paints its status dot from THEMES[theme].colors,
    // so the light theme showed one grey in the chrome and another in every label.
    muted: "#4A6172",
    primaryHex: "#1B7FE6",
    secondaryHex: "#0E93A5",
    successHex: "#15803D",
    warningHex: "#9A4A05",
    errorHex: "#B91C1C",
    infoHex: "#1D4ED8",
  },
  radius: DARK.radius,
  shadow: DARK.shadow,
  glassBlur: DARK.glassBlur,
  motion: DARK.motion,
  density: DARK.density,
};

export const THEMES: Record<"dark" | "light", ThemeValues> = {
  dark: DARK,
  light: LIGHT,
};

/**
 * The read-only iron law, machine-readable — the visual layer's share of the
 * authority chain (Observer projects, it never acts).
 *
 * assets/brand/design-tokens.json carries the same three values for consumers
 * that do not read TypeScript; the production-surface static contract compares
 * the two and fails on a disagreement, so this cannot drift into a decoration.
 */
export const VIEW_CONSTRAINTS = {
  readOnly: true,
  externalMutation: false,
  modelSummary: false,
} as const;

/* --------------------------------------------------------------------------
 * WUI-03 (20261009) · palettes.
 *
 * The 20261009 UI pack carries its own colour sheet. Per the owner's decision it does NOT replace the
 * shipped colours — the shipped pair above stays what a fresh session renders, and the pack's values
 * become a selectable palette (`?palette=master`). `src/index.css` declares the same numbers under
 * `html[data-palette="master"]`; src/theme/paletteMirror.contract.test.ts compares the two and fails on
 * a drift, and it also re-pins DARK/LIGHT so an overwrite would have to be deliberate.
 * ------------------------------------------------------------------------ */

export type PaletteId = "worklab" | "master";

/** What a session renders with no `?palette=` in the address. */
export const DEFAULT_PALETTE_ID: PaletteId = "worklab";

export interface PaletteSurface {
  bg: string;
  sidebar: string;
  panel: string;
  panel2: string;
  border: string;
  ink: string;
  muted: string;
}

/** The channels the pack names. It names no secondary (cyan) and no info, so neither appears here and
 *  neither is invented — the palette overlays what its source actually specifies. */
export interface PaletteAccents {
  primary: string;
  success: string;
  warning: string;
  error: string;
}

export const MASTER_PALETTE: Record<"dark" | "light", { surface: PaletteSurface; accents: PaletteAccents; label: string }> = {
  dark: {
    label: "母版建议 · 深色",
    surface: {
      bg: "#0B1018",
      sidebar: "#0E1520",
      panel: "#111C2B",
      panel2: "#17263A",
      border: "#2C3B50",
      ink: "#ECF2FA",
      muted: "#A4B2C6",
    },
    accents: { primary: "98 168 255", success: "105 213 181", warning: "255 200 120", error: "255 154 171" },
  },
  light: {
    label: "母版建议 · 浅色",
    // The pack gives sidebar and panel the SAME white and separates them with `line`; that is copied
    // verbatim rather than "improved", because a palette record that quietly differs from its source
    // is the drift this file exists to prevent.
    surface: {
      bg: "#F3F6FA",
      sidebar: "#FFFFFF",
      panel: "#FFFFFF",
      panel2: "#EAF0F7",
      border: "#CBD5E1",
      ink: "#172B46",
      muted: "#4F627A",
    },
    accents: { primary: "23 91 185", success: "20 107 83", warning: "135 83 9", error: "172 48 76" },
  },
};

export const PALETTE_LABELS: Record<PaletteId, string> = {
  worklab: "现行配色（默认）",
  master: "母版建议配色（20261009 包，可选）",
};

export function isPaletteId(value: string | null): value is PaletteId {
  return value === "worklab" || value === "master";
}

/* --------------------------------------------------------------------------
 * DAILY_SHELL_TOKENS (20261027) · the colour source of the two surfaces the desktop window shows.
 *
 * 日常壳 (?surface=daily) and the HUD 窄窗 (?surface=hud) used to paint 144+ hex literals of their own,
 * so `?theme=light` changed `html.class` and changed nothing the owner could see. They now paint from
 * the `--daily-*` variables in src/index.css, one name per role, declared in BOTH `:root` and
 * `html.light`; this record is the machine-readable copy of the same pair.
 *
 * Why this is a separate ramp and not `THEMES[…].colors`: the professional projection shell owns the
 * `--color-*` / `--bg` / `--surface` vocabulary, its values are pinned by DESIGN.md, skins/b10.css and
 * tokensMirror.contract.test.ts, and repainting the daily shell with them would be a second product
 * change smuggled into a colour pass. The roles below are the daily shell's own elevation ramp.
 *
 * src/daily/dailyThemeTokens.contract.test.ts asserts three things about this record: it equals the
 * sheet (per name, per theme), every light value differs from its dark partner (otherwise "follows the
 * theme" is a lie), and every text/role pair measures the WCAG ratio the legibility gate demands —
 * 4.5:1 for text, 3.0:1 for the 60%-opacity disabled label — in both themes.
 * ------------------------------------------------------------------------ */

export type DailyRole =
  | "bg" | "shell" | "surface" | "line" | "text" | "dim" | "disabledText"
  | "accent" | "onAccent" | "warnText" | "warnMark" | "warnLine"
  | "decisionMark" | "ok" | "accentTint" | "accentTintLine"
  | "warnTint" | "warnTintLine" | "scrim";

/** role -> the CSS custom property that carries it. Components reference `var(--daily-…)` only. */
export const DAILY_TOKEN_VARS: Record<DailyRole, string> = {
  bg: "--daily-bg",
  shell: "--daily-shell",
  surface: "--daily-surface",
  line: "--daily-line",
  text: "--daily-text",
  dim: "--daily-dim",
  disabledText: "--daily-disabled-text",
  accent: "--daily-accent",
  onAccent: "--daily-on-accent",
  warnText: "--daily-warn-text",
  warnMark: "--daily-warn-mark",
  warnLine: "--daily-warn-line",
  decisionMark: "--daily-decision-mark",
  ok: "--daily-ok",
  accentTint: "--daily-accent-tint",
  accentTintLine: "--daily-accent-tint-line",
  warnTint: "--daily-warn-tint",
  warnTintLine: "--daily-warn-tint-line",
  scrim: "--daily-scrim",
};

export type DailyRoles = Record<DailyRole, string>;

export const DAILY_TOKENS: Record<"dark" | "light", DailyRoles> = {
  dark: {
    bg: "#0D1219",
    shell: "#141B24",
    surface: "#1B242F",
    line: "#2A3441",
    text: "#E9EFF6",
    dim: "#A3B0C0",
    disabledText: "#AFBAC8",
    accent: "#45BFCF",
    onAccent: "#0A1016",
    warnText: "#FCD34D",
    warnMark: "#FBBF24",
    warnLine: "#FBBF24",
    decisionMark: "#FDE68A",
    ok: "#34D399",
    accentTint: "rgba(69, 191, 207, 0.14)",
    accentTintLine: "#1F5F6B",
    warnTint: "rgba(251, 191, 36, 0.10)",
    warnTintLine: "#6B5320",
    scrim: "rgba(6, 9, 13, 0.62)",
  },
  light: {
    // Every role changes. `accent` changes JOB as well as hue: the dark cyan is bright enough to read
    // as text (7.9:1 on the chrome) and to carry a near-black label as a fill (8.7:1), while the light
    // teal is deep enough to read on a white card (6.9:1) and to hold a white label (6.9:1).
    // `disabledText` is NOT the same colour as `dim` in this theme, and that is a measured decision:
    // skins/l10b-shell.css declares `button:disabled, button[aria-disabled="true"] { opacity: .55 }`,
    // which outranks the utility class, so the refusal label is painted at 55% — and this product holds
    // disabled copy to 3.0:1 instead of exempting it (WCAG does; a refusal the shell deliberately
    // displays must still be read). `dim` at 55% measured 2.86:1 and the legibility gate failed the light
    // daily-home surface with it, which is why the role exists at all.
    bg: "#F3F6FA",
    shell: "#E7EDF4",
    surface: "#FFFFFF",
    line: "#D2DBE6",
    text: "#14202E",
    dim: "#4F617A",
    disabledText: "#16243A",
    accent: "#086375",
    onAccent: "#FFFFFF",
    warnText: "#8A4A04",
    warnMark: "#B45309",
    warnLine: "#D9A05B",
    decisionMark: "#CA8A04",
    ok: "#12693A",
    accentTint: "rgba(8, 99, 117, 0.07)",
    accentTintLine: "#BAD8DE",
    warnTint: "rgba(138, 74, 4, 0.08)",
    warnTintLine: "#E7C9A6",
    scrim: "rgba(15, 23, 34, 0.42)",
  },
};

/** `var(--daily-<role>)` — the only form a component may paint with. */
export function dailyVar(role: DailyRole): string {
  return `var(${DAILY_TOKEN_VARS[role]})`;
}

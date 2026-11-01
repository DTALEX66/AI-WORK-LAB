/**
 * TOKENS MUST EQUAL WHAT THE SHEETS DECLARE (DESIGN.md Known Gaps 6 and 7).
 *
 * `src/theme/tokens.ts` opens by saying these values "MUST equal the CSS variable blocks in src/index.css
 * (:root dark + html.light)", and `tokens.test.ts` asserted them against literals copied from the same file —
 * so the pair could never disagree with each other and could both disagree with the browser. Two live
 * instances were found by measuring on 2026-10-08: `radius.sm` said 4px while the pinned skin's
 * `--radius-sm: 12px` wins the cascade (index.css loads before skins/b10.css), and `LIGHT.colors.muted` said
 * #5A7184 after the AA fix had moved the light muted role to #4A6172 — and that stale value *renders*, because
 * TopStatusBar paints its status dot from `THEMES[theme].colors`.
 *
 * These tests read the shipped sheets and compare, so the token record cannot drift from the pixels again
 * without a red test. The cross-sheet rule (one name, one value per theme across the three sheets) is
 * scripts/ci/verify_css_token_mirror.py; this file covers tokens.ts against those sheets.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { DARK, LIGHT, type ThemeAccentKey } from "./tokens";

const DECL = /(--[a-z0-9]+(?:-[a-z0-9]+)*)\s*:\s*([^;{}]+)/g;

/** Walk a sheet and return `theme::name` -> values, where theme comes from the enclosing selector. */
function readSheet(text: string, withoutComments = true): Map<string, string[]> {
  const source = withoutComments ? text.replace(/\/\*[\s\S]*?\*\//g, "") : text;
  const stack: string[] = [];
  const out = new Map<string, string[]>();
  let buffer = "";
  for (const ch of source) {
    if (ch === "{") {
      stack.push(buffer.trim().replace(/\s+/g, " "));
      buffer = "";
    } else if (ch === "}") {
      stack.pop();
      buffer = "";
    } else if (ch === ";") {
      const selector = stack[stack.length - 1] || "";
      const theme = /^html\.light/.test(selector) ? "light" : /^:root/.test(selector) ? "dark" : null;
      if (theme) {
        for (const match of buffer.matchAll(DECL)) {
          const key = `${theme}::${match[1]}`;
          const list = out.get(key) || [];
          list.push(canonical(match[2]));
          out.set(key, list);
        }
      }
      buffer = "";
    } else {
      buffer += ch;
    }
  }
  return out;
}

/** `rgba(0, 0, 0, 0.35)` and `rgba(0,0,0,.35)` are one value; only spelling differs. */
function canonical(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s*([(),])\s*/g, "$1")
    .replace(/-?\d*\.?\d+/g, (n) => `${Number(n)}`);
}

// vitest runs with the frontend directory as its working directory, which is how this file and
// `src/themeSwitch.contract.test.tsx` reach the sheets. `new URL(template, import.meta.url)` does not work
// here: Vite rewrites that form as an asset reference and hands back undefined for a dynamic path.
const sheets = ["src/index.css", "src/skins/b10.css", "src/skins/l10b-shell.css"].map((rel) =>
  readSheet(readFileSync(rel, "utf8")));

function css(theme: "dark" | "light", name: string): string[] {
  const found = sheets.flatMap((sheet) => sheet.get(`${theme}::${name}`) || []);
  // shape, motion and density tokens are theme-invariant: the sheets declare them once, in :root, and the
  // light block does not repeat them. Falling back to the dark declaration keeps the comparison honest
  // instead of inventing a requirement the sheets do not have.
  const inherited = found.length || theme !== "light"
    ? found
    : sheets.flatMap((sheet) => sheet.get(`dark::${name}`) || []);
  expect(inherited.length, `${name} is not declared in any sheet's ${theme} scope`).toBeGreaterThan(0);
  return [...new Set(inherited)];
}

function assertEqual(what: string, token: string, theme: "dark" | "light", name: string) {
  const values = css(theme, name);
  expect(values, `${name} declared ${values.length} different values in ${theme}`).toHaveLength(1);
  expect(canonical(token), `${what} (${theme}) disagrees with ${name} in the shipped sheets`).toBe(values[0]);
}

describe("tokens.ts mirrors the shipped sheets", () => {
  const surfaces: Array<[keyof typeof DARK.colors, string, string]> = [
    ["bg", "--color-bg", "--bg"],
    ["sidebar", "--color-sidebar", "--sidebar"],
    ["panel", "--color-panel", "--surface"],
    ["panel2", "--color-panel2", "--surface2"],
    ["border", "--color-border", "--border"],
    ["ink", "--color-ink", "--text"],
    ["muted", "--color-muted", "--muted"],
  ];

  for (const [key, colorVar, skinVar] of surfaces) {
    it(`dark.${key} equals both vocabularies`, () => {
      assertEqual(`colors.${key}`, DARK.colors[key], "dark", colorVar);
      assertEqual(`colors.${key}`, DARK.colors[key], "dark", skinVar);
    });
    it(`light.${key} equals both vocabularies`, () => {
      assertEqual(`colors.${key}`, LIGHT.colors[key], "light", colorVar);
      // the skin's own name keeps its dark value where the light sheet does not override it; only compare
      // it when a light scope declares it, otherwise the role is intentionally skin-invariant
      if (sheets.some((sheet) => sheet.has(`light::${skinVar}`))) {
        assertEqual(`colors.${key}`, LIGHT.colors[key], "light", skinVar);
      }
    });
  }

  const accents: Array<[ThemeAccentKey, string]> = [
    ["primary", "--primary-rgb"],
    ["secondary", "--secondary-rgb"],
    ["success", "--success-rgb"],
    ["warning", "--warning-rgb"],
    ["error", "--error-rgb"],
    ["info", "--info-rgb"],
  ];
  for (const [key, variable] of accents) {
    it(`${key} channels are the sheet's rgb triple in both themes`, () => {
      assertEqual(`accents.${key}`, DARK.accents[key], "dark", variable);
      assertEqual(`accents.${key}`, LIGHT.accents[key], "light", variable);
    });
  }

  it("the radius scale is what the sheets declare, including the step the pinned skin owns", () => {
    const steps: Array<[keyof typeof DARK.radius, string]> = [
      ["sm", "--radius-sm"], ["md", "--radius-md"], ["lg", "--radius-lg"], ["xl", "--radius-xl"],
    ];
    for (const [step, variable] of steps) {
      assertEqual(`radius.${step}`, DARK.radius[step], "dark", variable);
      assertEqual(`radius.${step}`, LIGHT.radius[step], "light", variable);
    }
    // sm is the case where index.css and skins/b10.css declare the same name: the token has to equal the
    // value that actually renders, which is the skin's, because main.tsx imports index.css before b10.css
    assertEqual("radius.sm against the pinned skin", DARK.radius.sm, "dark", "--radius-sm");
    expect(css("dark", "--radius-sm")).toEqual([canonical(DARK.radius.sm)]);
  });

  it("shadow and glass blur are the skin's values, not a paraphrase", () => {
    assertEqual("shadow", DARK.shadow, "dark", "--shadow");
    assertEqual("glassBlur", DARK.glassBlur, "dark", "--blur");
  });

  it("motion and density steps are the sheet's", () => {
    for (const [step, ms] of Object.entries(DARK.motion)) {
      assertEqual(`motion.${step}`, ms, "dark", `--motion-${step}`);
    }
    for (const [step, px] of Object.entries(DARK.density)) {
      assertEqual(`density.${step}`, px, "dark", `--density-${step}`);
    }
  });

  it("each theme's hex companions are the same colour as its channel triples", () => {
    // TopStatusBar paints from the *Hex fields while every CSS rule reads the channel form, so the two
    // spellings of one accent must not be different colours -- that is how the light warning amber stayed
    // readable in text and unreadable in the chrome at the same time.
    for (const [themeName, theme] of [["dark", DARK], ["light", LIGHT]] as const) {
      for (const [name, channels] of Object.entries(theme.accents) as Array<[ThemeAccentKey, string]>) {
        const hex = theme.colors[`${name}Hex` as keyof typeof theme.colors];
        expect(hex, `${themeName}.${name}Hex is missing`).toBeTruthy();
        const fromHex = [1, 3, 5].map((at) => Number.parseInt(hex.slice(at, at + 2), 16)).join(" ");
        expect(fromHex, `${themeName}.${name}Hex does not match ${name} channels`).toBe(channels);
      }
    }
  });

  it("the comparison itself distinguishes spelling from value", () => {
    // guards against a canonicaliser that equates different colours: 0.35 and 0.5 must stay distinct
    expect(canonical("rgba(0, 0, 0, 0.35)")).toBe(canonical("rgba(0,0,0,.35)"));
    expect(canonical("rgba(0,0,0,.35)")).not.toBe(canonical("rgba(0,0,0,0.5)"));
    expect(canonical("#4A6172")).toBe("#4a6172");
  });
});

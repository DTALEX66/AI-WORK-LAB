/**
 * DAILY_SHELL_TOKENS · the two desktop surfaces paint from the theme sheet, and the sheet is one record.
 *
 * Why this file exists (2026-10-27). 日常壳 (?surface=daily) and the HUD 窄窗 (?surface=hud) carried
 * ~200 hard-coded colour literals, so `?theme=light` wrote `html.class`, repainted the professional
 * shell, and left the screen an owner actually looks at byte-identical. The fix is not a better set of
 * literals — it is that these files must be unable to state a colour at all. Four things are pinned here:
 *
 * 1. MIRROR: `DAILY_TOKENS` in src/theme/tokens.ts equals the `--daily-*` declarations in src/index.css,
 *    per role, per theme — the same shape of guard `tokensMirror.contract.test.ts` is for `--color-*`.
 * 2. THE LIGHT HALF EXISTS AND MOVES: every role is declared in `:root` AND `html.light`, and every
 *    light value differs from its dark partner. "Follows the theme" is only a claim if the two sets of
 *    values are two sets; a light block that copies the dark numbers would keep the old bug while
 *    looking wired. This is also the assertion a planted fault has to trip (see the negative controls).
 * 3. BOTH THEMES ARE LEGIBLE, by measurement, not by intent: every text role against every backdrop it
 *    actually sits on (the three layers, each wash composited, the accent fill) recomputed with the WCAG
 *    maths `scripts/audit/text_legibility_via_cdp.py` applies — 4.5:1 for text, 3.0:1 for the label of a
 *    disabled control, which this product paints at 60% opacity and does NOT exempt.
 * 4. NO SECOND SOURCE: the three surface files state no colour value — no hex, no rgb()/rgba(), no
 *    Tailwind named shade (`text-amber-300` does not flip in light either, which is how the light pass
 *    would have failed on the honest screens) — and every `var(--…)` they use is a role this record
 *    owns, so a typo'd name cannot silently render nothing.
 *
 * The optional 母版 palette (`?palette=master`, WUI-03) is checked too: it must REACH these surfaces by
 * deriving the daily roles from its own named channels, and must not leak any pack value into the
 * default scopes. The owner's rule 配色不覆盖现行值 still decides which numbers a bare address renders.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { DAILY_TOKENS, DAILY_TOKEN_VARS, MASTER_PALETTE, type DailyRole } from "@/theme/tokens";

// vitest runs with the frontend directory as its cwd (see tokensMirror.contract.test.ts, which records
// why `new URL(…, import.meta.url)` cannot be used for these sheet reads here).
const CSS = readFileSync("src/index.css", "utf8");
const SURFACE_FILES = ["src/daily/DailyChrome.tsx", "src/daily/DailyApp.tsx", "src/daily/HudDaily.tsx"];

const DECL = /(--[a-z0-9]+(?:-[a-z0-9]+)*)\s*:\s*([^;{}]+)/g;

/** Walk the sheet and return the declarations whose innermost selector is exactly `selector`. */
function scope(selector: string): Map<string, string> {
  const source = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  const stack: string[] = [];
  let buffer = "";
  const out = new Map<string, string>();
  for (const ch of source) {
    if (ch === "{") { stack.push(buffer.trim().replace(/\s+/g, " ")); buffer = ""; }
    else if (ch === "}") { stack.pop(); buffer = ""; }
    else if (ch === ";") {
      if ((stack[stack.length - 1] || "") === selector) {
        for (const match of buffer.matchAll(DECL)) out.set(match[1], match[2].trim());
      }
      buffer = "";
    } else buffer += ch;
  }
  return out;
}

const ROOT_SCOPE = scope(":root");
const LIGHT_SCOPE = scope("html.light");
const MASTER_DARK = scope('html[data-palette="master"]');

const ROLES = Object.keys(DAILY_TOKEN_VARS) as DailyRole[];
/** every `--daily-*` name the sheet declares, so a role added to CSS alone cannot hide */
const SHEET_DAILY_NAMES = [...new Set([...ROOT_SCOPE.keys(), ...LIGHT_SCOPE.keys()])]
  .filter((name) => name.startsWith("--daily-"));

// --------------------------------------------------------------------- 1 · mirror

describe("daily tokens mirror the shipped sheet", () => {
  it("the sheet declares a daily ramp at all, in both modes", () => {
    expect(SHEET_DAILY_NAMES.length, "index.css declares no --daily-* ramp").toBeGreaterThanOrEqual(ROLES.length);
    expect(ROOT_SCOPE.size).toBeGreaterThanOrEqual(ROLES.length);
    expect(LIGHT_SCOPE.size).toBeGreaterThanOrEqual(ROLES.length);
  });

  it("every role in the record is declared in :root and in html.light", () => {
    for (const role of ROLES) {
      const name = DAILY_TOKEN_VARS[role];
      expect(ROOT_SCOPE.has(name), `${name} is missing from :root`).toBe(true);
      expect(LIGHT_SCOPE.has(name), `${name} is missing from html.light — a role with no light half is a role that cannot follow the theme`).toBe(true);
    }
  });

  it("the record equals the sheet, per role, per theme", () => {
    for (const role of ROLES) {
      const name = DAILY_TOKEN_VARS[role];
      expect(ROOT_SCOPE.get(name)?.toLowerCase(), `${name} (dark) disagrees with DAILY_TOKENS.dark`)
        .toBe(DAILY_TOKENS.dark[role].toLowerCase());
      expect(LIGHT_SCOPE.get(name)?.toLowerCase(), `${name} (light) disagrees with DAILY_TOKENS.light`)
        .toBe(DAILY_TOKENS.light[role].toLowerCase());
    }
  });

  it("a name the sheet declares is a name the record owns (no orphan role)", () => {
    const owned = new Set<string>(Object.values(DAILY_TOKEN_VARS));
    expect(SHEET_DAILY_NAMES.filter((name) => !owned.has(name))).toEqual([]);
  });
});

// --------------------------------------------------------------------- 2 · the light half really moves

describe("the daily ramp actually follows the theme", () => {
  it("no light role keeps its dark value", () => {
    const stuck = ROLES
      .filter((role) => DAILY_TOKENS.light[role].toLowerCase() === DAILY_TOKENS.dark[role].toLowerCase())
      .map((role) => DAILY_TOKEN_VARS[role]);
    expect(stuck, "these roles are identical in both themes, so switching to light changes nothing painted with them")
      .toEqual([]);
  });

  it("the layers stay three distinct steps in each theme (a flat ramp is the ugliness being fixed)", () => {
    for (const theme of ["dark", "light"] as const) {
      const layers = [DAILY_TOKENS[theme].bg, DAILY_TOKENS[theme].shell, DAILY_TOKENS[theme].surface];
      expect(new Set(layers).size, `${theme}: bg / shell / surface collapse into one colour`).toBe(3);
    }
  });

  it("the opt-in overlay reaches these surfaces by deriving, not by re-authoring", () => {
    // data-palette is absent by default, so :root/html.light alone decide what a bare address renders.
    // With ?palette=master the same roles must resolve to the pack's channels: asserted as DERIVED
    // references (var/color-mix/rgb of a pack channel), never a second literal ramp.
    for (const role of ROLES) {
      if (role === "scrim") continue;   // asserted separately below: a dimming layer darkens in any palette
      const name = DAILY_TOKEN_VARS[role];
      const overlay = MASTER_DARK.get(name);
      expect(overlay, `${name} is not reached by ?palette=master`).toBeTruthy();
      expect(/#[0-9a-fA-F]{3,8}/.test(overlay || ""), `${name}: the overlay re-authors a hex instead of deriving it`)
        .toBe(false);
      expect(/var\(--(color-[a-z0-9-]+|primary-rgb|warning-rgb|success-rgb)\)|color-mix|rgb\(/
        .test(overlay || ""), `${name}: the overlay does not reference the pack's own channels`).toBe(true);
    }
  });

  it("the overlay leaves the scrim alone, and re-declares nothing in the light half", () => {
    expect(MASTER_DARK.has("--daily-scrim"), "a scrim that follows the palette would stop dimming").toBe(false);
    // the master roles above are expressions over the pack's channels, and channels are re-declared by
    // html[data-palette="master"].light, so var() resolves per mode with no second copy of the ramp.
    const reDeclared = [...scope('html[data-palette="master"].light').keys()].filter((n) => n.startsWith("--daily-"));
    expect(reDeclared, "the light half of the overlay copied the ramp instead of deriving it").toEqual([]);
  });

  it("the shipped default ramp is not the pack's ramp (配色不覆盖现行值)", () => {
    // Compared by ROLE, not "is this hex anywhere in the pack": the pack's light ground and this ramp's
    // light ground are both a near-white #F3F6FA by coincidence, and an assertion that reads a
    // coincidence as a leak can never pass (paletteMirror.contract.test.ts records the same trap).
    const pairs: Array<[DailyRole, string]> = [
      ["bg", MASTER_PALETTE.dark.surface.bg], ["shell", MASTER_PALETTE.dark.surface.sidebar],
      ["surface", MASTER_PALETTE.dark.surface.panel], ["line", MASTER_PALETTE.dark.surface.border],
      ["text", MASTER_PALETTE.dark.surface.ink], ["dim", MASTER_PALETTE.dark.surface.muted],
    ];
    for (const [role, packValue] of pairs) {
      expect(DAILY_TOKENS.dark[role].toLowerCase(),
        `--daily-${role} now equals the pack: the optional palette was merged into the shipped ramp`)
        .not.toBe(packValue.toLowerCase());
    }
    // the sheet agrees, so the claim is about what renders and not only about the record
    expect(ROOT_SCOPE.get("--daily-bg")?.toLowerCase()).toBe(DAILY_TOKENS.dark.bg.toLowerCase());
    expect(ROOT_SCOPE.get("--daily-bg")?.toLowerCase()).not.toBe(MASTER_PALETTE.dark.surface.bg.toLowerCase());
  });
});

// --------------------------------------------------------------------- 3 · both themes are legible

type RGB = [number, number, number];

function parse(value: string): { rgb: RGB; alpha: number } {
  const text = value.trim();
  if (text.startsWith("#")) {
    const hex = text.slice(1);
    return { rgb: [0, 2, 4].map((at) => Number.parseInt(hex.slice(at, at + 2), 16)) as RGB, alpha: 1 };
  }
  const fn = /^rgba?\(([^)]+)\)$/.exec(text);
  if (!fn) throw new Error(`cannot parse token value ${value} — the gate would report this node UNKNOWN`);
  const parts = fn[1].split(/[\s,/]+/).filter(Boolean);
  return { rgb: [Number(parts[0]), Number(parts[1]), Number(parts[2])], alpha: parts[3] === undefined ? 1 : Number(parts[3]) };
}

/** the same maths as `channel_linear` / `relative_luminance` / `contrast_ratio` in the audit script */
function luminance([r, g, b]: RGB): number {
  const lin = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function contrast(a: RGB, b: RGB): number {
  const hi = Math.max(luminance(a), luminance(b));
  const lo = Math.min(luminance(a), luminance(b));
  return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100;
}
/** source-over, exactly as `over()` in the gate composites a translucent layer onto its backdrop */
function composite(fg: RGB, alpha: number, bg: RGB): RGB {
  return [0, 1, 2].map((i) => fg[i] * alpha + bg[i] * (1 - alpha)) as RGB;
}

const LAYER_ROLES = ["bg", "shell", "surface"] as const;
/** text role -> the backdrops it is painted on in the shipped markup */
const TEXT_PAIRS: Record<string, "layer" | "accentFill" | "disabledOnLayer"> = {
  text: "layer",
  dim: "layer",
  accent: "layer",
  warnText: "layer",
  ok: "layer",
  onAccent: "accentFill",
  disabledText: "disabledOnLayer",
};
/** a wash role -> the text role it carries (the chip / 失效条件 background) */
const WASHES: Array<[DailyRole, DailyRole]> = [
  ["accentTint", "accent"], ["accentTint", "dim"],
  ["warnTint", "warnText"], ["warnTint", "dim"],
];
// DailyChrome's DisabledAction carries an `opacity-60` utility, but skins/l10b-shell.css declares
// `button:disabled, button[aria-disabled="true"] { opacity: 0.55 }`, and a `:disabled` selector
// outranks a single class — the legibility gate measured 0.55 on the rendered label in both themes.
// The math is done at the value the user actually sees, not at the value the component asked for.
const DISABLED_OPACITY = 0.55;
const AA_TEXT = 4.5;
const AA_DISABLED = 3.0;

describe("every daily text role clears the floor in both themes", () => {
  for (const theme of ["dark", "light"] as const) {
    const T = DAILY_TOKENS[theme];
    it(`${theme}: plain text on each layer`, () => {
      for (const [role, kind] of Object.entries(TEXT_PAIRS)) {
        const fg = parse(T[role as DailyRole]);
        if (kind === "accentFill") {
          const bg = parse(T.accent).rgb;
          expect(contrast(fg.rgb, bg), `${role} on the accent fill (${theme})`).toBeGreaterThanOrEqual(AA_TEXT);
          continue;
        }
        if (kind === "disabledOnLayer") {
          for (const layer of LAYER_ROLES) {
            const bg = parse(T[layer]).rgb;
            const painted = composite(fg.rgb, DISABLED_OPACITY, bg);
            expect(contrast(painted, bg),
              `${role} painted at ${DISABLED_OPACITY * 100}% opacity on ${layer} (${theme}) — this product does not exempt disabled copy`)
              .toBeGreaterThanOrEqual(AA_DISABLED);
          }
          continue;
        }
        for (const layer of LAYER_ROLES) {
          expect(contrast(fg.rgb, parse(T[layer]).rgb), `${role} on ${layer} (${theme})`)
            .toBeGreaterThanOrEqual(AA_TEXT);
        }
      }
    });

    it(`${theme}: text on a composited wash, worst case over every layer`, () => {
      for (const [wash, role] of WASHES) {
        for (const layer of LAYER_ROLES) {
          const w = parse(T[wash]);
          const composited = composite(w.rgb, w.alpha, parse(T[layer]).rgb);
          const ratio = contrast(parse(T[role]).rgb, composited);
          expect(ratio, `${role} text on ${wash} over ${layer} (${theme})`).toBeGreaterThanOrEqual(AA_TEXT);
        }
      }
    });

    it(`${theme}: a token the gate cannot parse is an UNKNOWN and an UNKNOWN fails the gate`, () => {
      for (const role of ROLES) {
        expect(() => parse(DAILY_TOKENS[theme][role]), `${DAILY_TOKEN_VARS[role]} (${theme})`).not.toThrow();
      }
    });
  }
});

// --------------------------------------------------------------------- 4 · no second source of colour

describe("the surfaces state no colour of their own", () => {
  it("no hex, no rgb()/rgba(), no Tailwind named shade in the three surface files", () => {
    for (const file of SURFACE_FILES) {
      const text = readFileSync(file, "utf8");
      const hex = text.match(/#[0-9a-fA-F]{3,8}\b/g) || [];
      expect(hex, `${file} still carries hex literals: ${hex.slice(0, 6)}`).toEqual([]);
      const funcs = text.match(/\b(?:rgba?|hsla?)\(/g) || [];
      expect(funcs, `${file} paints a raw colour function: ${funcs}`).toEqual([]);
      const named = text.match(
        /\b(?:bg|text|border|divide|fill|stroke|ring|from|to|via|placeholder|shadow)-(?:amber|yellow|orange|lime|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|red|green|slate|gray|zinc|neutral|stone|black|white)(?:-\d{2,3})?(?:\/\d{1,2})?\b/g,
      ) || [];
      expect(named, `${file} uses Tailwind shade classes, which do not flip with html.light: ${named.slice(0, 8)}`)
        .toEqual([]);
    }
  });

  it("every arbitrary colour class the surfaces use resolves to a daily role this record owns", () => {
    const owned = new Set<string>(Object.values(DAILY_TOKEN_VARS));
    for (const file of SURFACE_FILES) {
      const text = readFileSync(file, "utf8");
      const refs = [...text.matchAll(/var\(\s*(--[a-z0-9-]+)\s*\)/g)].map((m) => m[1]);
      // DailyChrome builds most of its references through dailyVar(), so the floor is "this file speaks
      // token at all", not a count that a refactor would break; the no-literal rule above is the load-
      // bearing one.
      expect(refs.length, `${file} paints with no token at all`).toBeGreaterThanOrEqual(3);
      const foreign = refs.filter((name) => !owned.has(name));
      expect(foreign, `${file} references variables no daily role owns: ${[...new Set(foreign)]}`).toEqual([]);
    }
  });

  it("the shared palette object T carries var() references only", async () => {
    const { T } = await import("@/daily/DailyChrome");
    for (const role of ROLES) {
      expect((T as Record<string, string>)[role], `T.${role} must be a token reference`)
        .toBe(`var(${DAILY_TOKEN_VARS[role]})`);
    }
  });
});

// --------------------------------------------------------------------- negative controls

describe("the guards above can actually see a regression", () => {
  /** the predicate the real test uses, factored out so a planted fault proves it fires */
  const stuckRoles = (dark: Record<string, string>, light: Record<string, string>) =>
    ROLES.filter((role) => light[role].toLowerCase() === dark[role].toLowerCase())
      .map((role) => DAILY_TOKEN_VARS[role]);

  it("the real ramp has no stuck role", () => {
    expect(stuckRoles(DAILY_TOKENS.dark, DAILY_TOKENS.light)).toEqual([]);
  });

  it("copying one dark value into the light half is convicted by name", () => {
    // This is the fault the owner asked to plant: html.light's ink set equal to the dark ink. The
    // detector must name that role, and it must still pass a ramp that only looks close.
    const planted = { ...DAILY_TOKENS.light, text: DAILY_TOKENS.dark.text };
    expect(stuckRoles(DAILY_TOKENS.dark, planted)).toEqual(["--daily-text"]);
    const nearMiss = { ...DAILY_TOKENS.light, text: DAILY_TOKENS.light.text.replace(/E$/, "F") };
    expect(stuckRoles(DAILY_TOKENS.dark, nearMiss)).toEqual([]);
  });

  it("a light ink copied from the dark half also fails the measured contrast rule", () => {
    // the second, independent trip-wire: the dark ink #E9EFF6 on the light ground #F3F6FA is the pair
    // the gate would convict, so the same fault cannot hide behind the equality check alone.
    const darkInk = parse(DAILY_TOKENS.dark.text).rgb;
    const lightGround = parse(DAILY_TOKENS.light.bg).rgb;
    expect(contrast(darkInk, lightGround)).toBeLessThan(AA_TEXT);
  });

  it("the contrast helper reproduces a known ratio, so a broken helper cannot certify a bad palette", () => {
    // the pair the old honesty note quoted for itself: #A6B0BE on #10141A measured 8.42:1.
    expect(contrast(parse("#A6B0BE").rgb, parse("#10141A").rgb)).toBe(8.42);
    // and it separates a readable pair from an unreadable one
    expect(contrast(parse("#FFFFFF").rgb, parse("#F3F6FA").rgb)).toBeLessThan(1.2);
    expect(contrast(parse("#14202E").rgb, parse("#FFFFFF").rgb)).toBeGreaterThan(16);
  });

  it("the scope walker reads the daily ramp and nothing else", () => {
    expect(SHEET_DAILY_NAMES.length).toBe(ROLES.length);
    expect([...ROOT_SCOPE.keys()].filter((n) => n.startsWith("--color-")).length).toBe(7);
    expect(ROOT_SCOPE.get("--color-bg")?.toLowerCase()).toBe("#050d16");
    expect(LIGHT_SCOPE.get("--color-bg")?.toLowerCase()).toBe("#f4f7fa");
  });

  it("the master overlay does not cover the shipped defaults", () => {
    // the pack's own dark ground differs from the shipped daily ground, and the default scope keeps the
    // shipped one — if someone merged the pack into :root, both assertions would break together.
    expect(MASTER_PALETTE.dark.surface.bg.toLowerCase()).not.toBe(DAILY_TOKENS.dark.bg.toLowerCase());
    expect(ROOT_SCOPE.get("--daily-bg")?.toLowerCase()).toBe(DAILY_TOKENS.dark.bg.toLowerCase());
  });
});

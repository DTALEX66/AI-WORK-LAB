/**
 * WUI-03 · the palette overlay mirrors its token record, and the shipped colours are guarded.
 *
 * Two opposite failures are pinned here on purpose:
 *
 * 1. the `master` record and the `html[data-palette="master"]` block disagreeing — the same shape of bug
 *    that `tokensMirror.contract.test.ts` exists for, one level up;
 * 2. the pack's colours leaking into the DEFAULT sheets. The owner's instruction is 配色不覆盖现行值, so a
 *    pack hex appearing under `:root` or `html.light` is not a style choice, it is the decision being
 *    reversed by someone who read the pack and not the instruction. Both the token literals and the
 *    shipped sheet values are re-pinned, and the pack's values are asserted ABSENT from the default scope.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { DARK, LIGHT, MASTER_PALETTE, DEFAULT_PALETTE_ID, PALETTE_LABELS,
  type PaletteAccents, type PaletteSurface } from "./tokens";
import { readPaletteParam, applyPalette, PALETTE_ATTRIBUTE } from "./paletteMode";

// vitest runs with the frontend directory as its working directory (see tokensMirror.contract.test.ts,
// which records why `new URL(..., import.meta.url)` is rewritten into an asset reference here).
const CSS = readFileSync("src/index.css", "utf8");
const HTML = readFileSync("index.html", "utf8");

const DECL = /(--[a-z0-9]+(?:-[a-z0-9]+)*)\s*:\s*([^;{}]+)/g;

/** Every custom-property declaration in the sheet, tagged with its innermost selector.
 *  Same walk `tokensMirror.contract.test.ts` uses, so the two files cannot disagree about what a scope is. */
function declarations(): { selector: string; name: string; value: string }[] {
  const source = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  const out: { selector: string; name: string; value: string }[] = [];
  const stack: string[] = [];
  let buffer = "";
  for (const ch of source) {
    if (ch === "{") { stack.push(buffer.trim().replace(/\s+/g, " ")); buffer = ""; }
    else if (ch === "}") { stack.pop(); buffer = ""; }
    else if (ch === ";") {
      const selector = stack[stack.length - 1] || "";
      for (const match of buffer.matchAll(DECL)) {
        out.push({ selector, name: match[1], value: match[2].trim().toLowerCase() });
      }
      buffer = "";
    } else buffer += ch;
  }
  return out;
}

const ALL = declarations();

function scope(selector: RegExp): Map<string, string> {
  const out = new Map<string, string>();
  for (const entry of ALL) if (selector.test(entry.selector)) out.set(entry.name, entry.value);
  return out;
}

const masterDark = scope(/^html\[data-palette="master"\]$/);
const masterLight = scope(/^html\[data-palette="master"\]\.light$/);
const shippedDark = scope(/^:root$/);
const shippedLight = scope(/^html\.light$/);

/** The variables the overlay touches, keyed by name so neither test has to cast a record to `any`. */
const SURFACE_VARS: { name: string; key: keyof PaletteSurface }[] = [
  { name: "--color-bg", key: "bg" }, { name: "--color-sidebar", key: "sidebar" },
  { name: "--color-panel", key: "panel" }, { name: "--color-panel2", key: "panel2" },
  { name: "--color-border", key: "border" }, { name: "--color-ink", key: "ink" },
  { name: "--color-muted", key: "muted" },
];
const ACCENT_VARS: { name: string; key: keyof PaletteAccents }[] = [
  { name: "--primary-rgb", key: "primary" }, { name: "--success-rgb", key: "success" },
  { name: "--warning-rgb", key: "warning" }, { name: "--error-rgb", key: "error" },
];

describe("WUI-03 · master palette record ↔ sheet", () => {
  it("the sheet exists at all, in both modes, under the attribute the code sets", () => {
    // The first build set `palette` while the sheet matched `[data-palette]`. Every text assertion stayed
    // green and the opt-in theme rendered exactly like the default — so the NAME is asserted here, from
    // the same constant the code uses, not from a string copied twice.
    expect(CSS).toContain(`html[${PALETTE_ATTRIBUTE}="master"]`);
    expect(masterDark.size, "index.css declares no palette overlay block").toBeGreaterThan(0)
    expect(masterLight.size, "index.css declares no light half of the palette").toBeGreaterThan(0)
  })

  it("every recorded colour is what the sheet declares, dark and light", () => {
    for (const [record, sheet] of [[MASTER_PALETTE.dark, masterDark], [MASTER_PALETTE.light, masterLight]] as const) {
      for (const { name, key } of SURFACE_VARS) {
        expect(sheet.get(name), `${name}`).toBe(record.surface[key].toLowerCase());
      }
      for (const { name, key } of ACCENT_VARS) {
        expect(sheet.get(name), `${name}`).toBe(record.accents[key]);
      }
    }
  })

  it("the channels the pack does not name are NOT re-declared by the overlay", () => {
    // An absent value is a stated gap; inventing a cyan or an info tint the pack never specified would
    // turn a suggestion into a second design authority.
    for (const sheet of [masterDark, masterLight]) {
      expect(sheet.has("--secondary-rgb")).toBe(false)
      expect(sheet.has("--info-rgb")).toBe(false)
      expect(sheet.has("--radius-sm")).toBe(false)
      expect(sheet.has("--motion-base")).toBe(false)
    }
  })
})

describe("WUI-03 · the shipped palette is what a default session renders", () => {
  it("the shipped tokens still hold the measured values", () => {
    // #050D16 / #F4F7FA are not decoration: the light muted role in particular moved to #4A6172 because
    // the earlier grey measured 4.43:1 on a panel2 surface and failed AA.
    expect(DARK.colors.bg).toBe("#050D16");
    expect(DARK.colors.muted).toBe("#8EABBC");
    expect(LIGHT.colors.bg).toBe("#F4F7FA");
    expect(LIGHT.colors.muted).toBe("#4A6172");
    expect(LIGHT.accents.warning).toBe("154 74 5");
    expect(DEFAULT_PALETTE_ID).toBe("worklab");
    expect(PALETTE_LABELS.worklab).toContain("默认");
  })

  it("the default scopes still declare the shipped values for every variable the pack touches", () => {
    // Compared per NAME, not "is this hex anywhere in the pack": the pack's light `panel` and the shipped
    // light `panel` are both #FFFFFF, and an assertion that reads a coincidence as a leak can never pass
    // — it only teaches whoever hits it to delete the guard.
    let differsFromPack = 0;
    for (const [sheet, tokens, pack] of [
      [shippedDark, DARK, MASTER_PALETTE.dark], [shippedLight, LIGHT, MASTER_PALETTE.light],
    ] as const) {
      for (const { name, key } of SURFACE_VARS) {
        expect(sheet.get(name), `${name} no longer matches theme/tokens.ts`).toBe(
          tokens.colors[key].toLowerCase());
        if (sheet.get(name) !== pack.surface[key].toLowerCase()) differsFromPack += 1;
      }
      for (const { name, key } of ACCENT_VARS) {
        expect(sheet.get(name), `${name}`).toBe(tokens.accents[key]);
        if (sheet.get(name) !== pack.accents[key]) differsFromPack += 1;
      }
    }
    // The falsification half: if the pack had been merged into the defaults, every assertion above would
    // still pass and this count would be zero.
    expect(differsFromPack, "the default sheets now equal the pack — the palette was overwritten, not added")
      .toBeGreaterThan(4);
  })

  it("the address is the only state carrier, before and after mount", () => {
    expect(readPaletteParam("")).toBe("worklab")
    expect(readPaletteParam("?palette=master")).toBe("master")
    // an unknown value is not a palette: it must not resolve to the pack by accident
    expect(readPaletteParam("?palette=MaStEr")).toBe("worklab")
    expect(readPaletteParam("?palette=" + encodeURIComponent("../../etc/passwd"))).toBe("worklab")

    const root = document.createElement("div");
    applyPalette(root, "worklab");
    expect(root.hasAttribute(PALETTE_ATTRIBUTE)).toBe(false)
    applyPalette(root, "master");
    expect(root.getAttribute(PALETTE_ATTRIBUTE)).toBe("master")
    applyPalette(root, "worklab");
    expect(root.hasAttribute(PALETTE_ATTRIBUTE)).toBe(false)
  })

  it("index.html projects the same rule before React mounts", () => {
    // Parity with the theme's pre-render contract (B3/U05): without this line the palette would flash.
    expect(HTML).toMatch(/get\('palette'\)\s*===\s*'master'/)
    expect(HTML).toMatch(new RegExp(`setAttribute\\('${PALETTE_ATTRIBUTE}',\\s*'master'\\)`))
    expect(HTML).not.toMatch(/localStorage/)
  })
})

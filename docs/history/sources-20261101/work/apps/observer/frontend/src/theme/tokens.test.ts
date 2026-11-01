import { describe, expect, it } from "vitest";
import { DARK, LIGHT, THEMES } from "./tokens";

/**
 * UI_TOKENS: assert the token single-source-of-truth against the B10/L4/L7
 * authority (three-way identical). These values MUST equal the CSS variable
 * blocks in src/index.css (:root dark + html.light).
 */
describe("theme tokens", () => {
  it("dark: accents are the B10 authoritative RGB channels", () => {
    expect(DARK.accents.primary).toBe("42 145 255"); // #2A91FF
    expect(DARK.accents.secondary).toBe("32 205 225"); // #20CDE1 cyan, NOT purple
    expect(DARK.accents.success).toBe("34 197 94");
    expect(DARK.accents.warning).toBe("245 158 11");
    expect(DARK.accents.error).toBe("239 68 68");
    expect(DARK.accents.info).toBe("56 130 246");
  });

  it("dark: surfaces are the deep-navy console palette", () => {
    expect(DARK.colors.bg).toBe("#050D16");
    expect(DARK.colors.sidebar).toBe("#07111C");
    expect(DARK.colors.panel).toBe("#081420");
    expect(DARK.colors.panel2).toBe("#0C1B2A");
    expect(DARK.colors.border).toBe("#17435D");
    expect(DARK.colors.ink).toBe("#EEF6FC");
    expect(DARK.colors.muted).toBe("#8EABBC");
  });

  it("dark: shape/motion/density match L4 + L6", () => {
    expect(DARK.radius).toEqual({ sm: "12px", md: "10px", lg: "16px", xl: "22px" });
    expect(DARK.shadow).toBe("0 20px 80px rgba(0, 0, 0, 0.35)");
    expect(DARK.glassBlur).toBe("18px");
    expect(DARK.motion.fast).toBe("120ms");
    expect(DARK.motion.modal).toBe("220ms");
    expect(DARK.motion.drawer).toBe("280ms");
    expect(DARK.motion.emphasis).toBe("420ms");
    expect(DARK.density).toEqual({ comfortable: "68px", default: "56px", compact: "44px" });
  });

  it("light: accents are deepened for light-surface contrast", () => {
    expect(LIGHT.accents.primary).toBe("27 127 230");
    expect(LIGHT.accents.secondary).toBe("14 147 165");
    expect(LIGHT.colors.bg).toBe("#F4F7FA");
    expect(LIGHT.colors.ink).toBe("#0B1420");
    expect(LIGHT.colors.muted).toBe("#4A6172");
  });

  it("neither theme carries the legacy purple accent (#7C6CF0 = 124 108 240)", () => {
    for (const theme of Object.values(THEMES)) {
      for (const [name, channels] of Object.entries(theme.accents)) {
        expect(channels, `accent ${name}`).not.toContain("124 108 240");
        expect(channels, `accent ${name}`).not.toMatch(/7C6CF0/i);
        // structural check: channels must be exactly three RGB integers
        expect(channels).toMatch(/^\d{1,3} \d{1,3} \d{1,3}$/);
      }
      // no purple hex anywhere in the color surfaces
      const surfaceDump = JSON.stringify(theme.colors);
      expect(surfaceDump).not.toMatch(/7C6CF0|6D5EF0/i);
    }
  });

  it("THEMES exposes both and shares shape tokens (radius/motion are theme-invariant)", () => {
    expect(THEMES.dark.radius).toBe(LIGHT.radius);
    expect(THEMES.dark.motion).toBe(LIGHT.motion);
  });
});

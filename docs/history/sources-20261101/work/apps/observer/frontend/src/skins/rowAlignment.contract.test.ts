/**
 * WUI-03 · stacked detail rows must actually stretch.
 *
 * `align-items` on a `.list-item` is decided by load order, and load order is exactly what the last two
 * cascade bugs in this skin turned on: `src/main.tsx` imports `index.css` (Tailwind utilities, where
 * `items-stretch` lives) BEFORE `skins/b10.css`, so a one-class `.list-item{align-items:center}` in the
 * pinned skin beats a one-class utility of equal specificity that arrived earlier. The result was
 * invisible to every text and contrast assertion — the label and the value were both present, they were
 * just centered, which is what the row layout was never meant to look like.
 *
 * So the guard is on the cascade itself: the shell must re-assert the alignment for a stacked row, and it
 * must keep doing so only while the pinned skin still fights it. If b10 stops declaring `align-items` on
 * `.list-item`, this test says the override is now unexplained rather than letting it rot into dead CSS.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const SHELL = readFileSync("src/skins/l10b-shell.css", "utf8");
const B10 = readFileSync("src/skins/b10.css", "utf8");
const MAIN = readFileSync("src/main.tsx", "utf8");

/** b10's `.list-item` block, comments stripped. */
function listItemRule(source: string): string {
  const stripped = source.replace(/\/\*[\s\S]*?\*\//g, "");
  const match = /\.list-item\s*\{([^}]*)\}/.exec(stripped);
  return match ? match[1] : "";
}

describe("stacked row alignment (WUI-03)", () => {
  it("the pinned skin still centers list items, so an override is genuinely needed", () => {
    expect(listItemRule(B10)).toMatch(/align-items:\s*center/);
  });

  it("the shell layer re-asserts stretch and left alignment for a stacked row", () => {
    const override = /\.list-item\.flex-col\s*\{([^}]*)\}/.exec(
      SHELL.replace(/\/\*[\s\S]*?\*\//g, ""));
    expect(override, "the shell no longer overrides alignment for stacked rows").not.toBeNull();
    expect(override![1]).toMatch(/align-items:\s*stretch/);
    expect(override![1]).toMatch(/text-align:\s*left/);
  });

  it("the override is two classes deep, which is the only reason it wins", () => {
    // A one-class rule here would tie `.list-item` and lose on order; the second class is load-bearing.
    expect(SHELL).toMatch(/\.list-item\.flex-col\s*\{/);
  });

  it("the import order that created the problem is still the shipped one", () => {
    const indexAt = MAIN.indexOf("index.css");
    const b10At = MAIN.indexOf("skins/b10.css");
    const shellAt = MAIN.indexOf("skins/l10b-shell.css");
    expect(indexAt).toBeGreaterThanOrEqual(0);
    expect(b10At).toBeGreaterThan(indexAt);
    expect(shellAt).toBeGreaterThan(b10At);
  });
})

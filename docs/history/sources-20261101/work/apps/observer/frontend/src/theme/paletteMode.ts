// WUI-03 · the palette dimension, kept orthogonal to the light/dark mode.
//
// The owner's rule for the 20261009 pack is 配色不覆盖现行值, so the pack's colours are a SELECTABLE
// palette rather than a replacement: `?palette=master` opts in, and a bare address renders exactly what
// shipped before this module existed. Two details make that promise hold:
//
// * the attribute is ABSENT for the default palette. An explicit `data-palette="worklab"` would be a
//   second way to say the same thing, and the day someone restyles `[data-palette]` the default would
//   silently stop matching the sheet it is supposed to inherit;
// * the value is read from the URL and nothing else. Web storage is forbidden in this UI layer
//   (test_production_surface_static_contract.js), so a shared address reproduces the pixels.
import { DEFAULT_PALETTE_ID, isPaletteId, type PaletteId } from './tokens'

export const PALETTE_PARAM = 'palette'
/** The attribute `src/index.css` selects the overlay with. It is `data-palette`, not `palette`: the first
 *  build of this module set the short name, the sheet matched the long one, and the opt-in palette
 *  rendered pixel-identical to the default — invisible to every text assertion, visible the moment the
 *  screenshot was opened. */
export const PALETTE_ATTRIBUTE = 'data-palette'

/** The palette an address asks for. Anything not named — including a typo — is the shipped default,
 *  which is what keeps an old link rendering the colours it was saved with. */
export function readPaletteParam(search: string): PaletteId {
  try {
    const raw = new URLSearchParams(search).get(PALETTE_PARAM)
    return isPaletteId(raw) ? raw : DEFAULT_PALETTE_ID
  } catch {
    return DEFAULT_PALETTE_ID
  }
}

/** Project the palette onto the document, the same way the theme is projected: one attribute, no class
 *  pile-up, and the default path leaves the element untouched. */
export function applyPalette(root: HTMLElement, palette: PaletteId): void {
  if (palette === DEFAULT_PALETTE_ID) root.removeAttribute(PALETTE_ATTRIBUTE)
  else root.setAttribute(PALETTE_ATTRIBUTE, palette)
}

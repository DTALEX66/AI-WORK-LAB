# CJK typography baseline

Chinese, Japanese and Korean typography must be treated as separate writing systems with shared implementation concerns, not one generic style.

- Validate font glyph coverage, punctuation behavior, line breaking and fallback per language.
- Avoid Latin-centric letter-spacing and all-caps logic on CJK text.
- Define mixed-script baselines, numeral roles, punctuation compression and vertical-writing behavior where relevant.
- Test Simplified Chinese, Traditional Chinese, Japanese and Korean samples independently.
- Do not use unlicensed CJK fonts; record font file, license and permitted embedding/subsetting.
- For Chinese commercial design, explicitly test short headlines, dense body copy, vertical titles, numbers/units and bilingual lockups.

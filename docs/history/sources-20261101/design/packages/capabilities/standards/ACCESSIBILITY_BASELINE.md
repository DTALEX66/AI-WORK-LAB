# Accessibility baseline

## Digital artifacts

- Target WCAG 2.2 AA unless the brief or law requires more.
- Use semantic HTML first; ARIA supplements semantics and never repairs broken interaction by itself.
- Every interactive component defines keyboard behavior, focus visibility, disabled/loading/error/success states and screen-reader labels.
- Contrast, target size, reflow, zoom, non-text contrast, error identification and accessible authentication are explicit checks.
- Automated scans are necessary but incomplete; keyboard, screen-reader and cognitive review remain human gates.

## Documents

- Reading order, headings, language, tagged structure, alt text, table headers, links and bookmarks are checked.
- Print-ready and accessible PDF are separate profiles; when both are required, record the target PDF/X/PDF/UA/PDF/A combination and validator evidence.
  - **出处状态（2026-10-22）**：这一条是本项目自己的**做法**（分剖面记录 + 记录校验器证据），不是对外部规范的引用，因此不需要出版方出处；但"PDF/UA"这个名字背后的 ISO 14289-1 版次**仍未向出版方取证**（两轮取数全被挡，见 `INDUSTRY_SPEC_REGISTER.md` C 档）。在拿到出版方页面之前，交付记录里可以写"按 PDF/UA 剖面校验并附 validator 证据"，**不得**写"符合 ISO 14289-1:YYYY"这类带版次的合规断言。

## Physical/spatial

- Apply jurisdiction-specific building/accessibility codes.
- Validate reach ranges, circulation, seating, text size/viewing distance, glare, contrast, tactile/audio alternatives and emergency wayfinding.

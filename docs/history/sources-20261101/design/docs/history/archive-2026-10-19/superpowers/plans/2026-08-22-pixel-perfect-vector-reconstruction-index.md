# Pixel-Perfect Vector Reconstruction — Execution Index

This index implements the approved
[`2026-08-22-pixel-perfect-vector-reconstruction-design.md`](../specs/2026-08-22-pixel-perfect-vector-reconstruction-design.md)
through four independently reviewable plans.

Execute them in order:

1. [`2026-08-22-vector-reconstruction-deterministic-core.md`](2026-08-22-vector-reconstruction-deterministic-core.md)
   — a complete local RIR → SVG → preview → metric pipeline with no AI or Adobe dependency.
2. [`2026-08-22-vector-reconstruction-ai-decomposition.md`](2026-08-22-vector-reconstruction-ai-decomposition.md)
   — bounded model providers, OCR, semantic layers, vector candidates, font matching, and hybrid fusion.
3. [`2026-08-22-vector-reconstruction-adobe-adapters.md`](2026-08-22-vector-reconstruction-adobe-adapters.md)
   — Illustrator native assembly/read-back and optional Photoshop UXP preparation.
4. [`2026-08-22-vector-reconstruction-hardening-release.md`](2026-08-22-vector-reconstruction-hardening-release.md)
   — adversarial safety, six-case qualification, reproducibility, recovery, performance, and release evidence.

Each plan must end with a clean diff review and its listed local gates. Publication, model download,
Adobe installation, remote inference, and live host writes remain separately authorized side effects.

Execution is also bound by the preflight rulings in
[`2026-08-23-pixel-perfect-vector-reconstruction-execution-rulings.md`](2026-08-23-pixel-perfect-vector-reconstruction-execution-rulings.md).
Those rulings close specification gaps discovered before Task 1 and add one deterministic bundle/evidence
packaging task, making the executable total 20 tasks.

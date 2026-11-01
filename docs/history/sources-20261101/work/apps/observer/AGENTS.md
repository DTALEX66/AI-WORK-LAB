# Observer module rules

- Observer is **strictly read-only** with respect to external systems and all authoritative module state.
- Observer is a **consumer of the Canonical Projection**, never a producer of authoritative events.
- The single writer / producer of telemetry events is **Workflow Assistance** (`packages/client-neutral-core`); it owns the Telemetry Ledger.
- Observer writes only its own derived cache/projection/report artifacts under project-local ignored runtime paths, and only for rendering — it does not append authoritative events.
- Do not add execution, approval, configuration-apply, Git mutation, shell, or hidden deep-link routes.
- Do not read credentials, cookies, auth stores, prompt/response bodies, private memory, session databases, or model weights.
- Keep one writer per checkout and preserve existing user changes.
- Structural checks and isolated projections are not live desktop or external-system evidence.

# Real-case full-stack evidence matrix

Use this reference when the request says “all real cases” or requires both backend and frontend proof.

## Evidence layers

| Layer | Required proof | Do not substitute |
|---|---|---|
| Case inventory | Enumerate the named chains and the test functions/fixtures that represent them | A historical package count or an unlabeled aggregate total |
| Backend chain | Run the current `integration-tests/test_real_case_e2e.py` and preserve its exact result | Calling a few service functions manually |
| Backend HTTP | Start FastAPI after migration on an isolated project-local data root; intake web, GitHub, and file fixtures through HTTP; read status/jobs/research from the same database | TestClient-only results or a browser mock |
| Frontend | Use Playwright against that same server and same database; submit a real UI form and read the resulting queue/status projection | Static HTML inspection or mocked fetch responses |
| Redaction | Assert that user-facing JSON and rendered text do not contain package/job/command/unit/artifact IDs | Assuming a serializer is safe because the page looks correct |
| Lifecycle UI boundary | Distinguish backend chains that pass from lifecycle pages that are still unavailable in the product UI | Claiming every backend chain has a frontend screen |

## Temporary harness rules

- Keep the runner under `.hermes/task-runtime/`; never add it to Git.
- Match the repository fetcher contract exactly: accept positional `url` plus optional policy/headers, then `**kwargs` if needed. A fixture that only accepts `**kwargs` can fail before product code is exercised.
- Inspect `app/workspace/ui/index.html` before writing selectors. The current Research container is `#research-queue`, not `#research-list`.
- Playwright `locator.wait_for()` returns `None`; call it as a synchronization step, then assert a separate observable value if needed.
- Use a fresh `COGNITIVE_DATA_DIR` for each rerun after a failed harness so stale partial records cannot make counts ambiguous.
- Set `Session.trust_env = False` or equivalent loopback proxy bypass for local HTTP requests.

## Stateful UI convergence checks

For every case row, test the transition rather than merely the presence of a button:

```text
pending source visible
→ semantic approve action
→ approve response contains only product DTO fields
→ source disappears from pending queue
→ next lifecycle projection contains exactly that source
→ repeated action is idempotent or returns a controlled conflict
```

Use source-bound actions in the product contract. Do not select a case by button position or pass `package_id`, `unit_id`, `artifact_id`, or other persistence IDs through the ordinary browser. If generated candidate titles are shared by multiple cases, make the title/projection source-specific before attempting multi-case Runtime approval; otherwise a uniqueness guard correctly rejects the action but the UI cannot finish the matrix.

Run the official migration command against a fresh isolated data root before starting FastAPI. A fail-closed “schema has not been migrated” startup is a harness prerequisite failure, not evidence that the product route is broken. Browser scripts must also close modal dialogs before navigating; a successful form submission does not necessarily dismiss the modal.

A passing backend E2E count still does not satisfy this matrix. The browser must drive the same cases through Research, Knowledge, Learning, Practice/Mastery and governed Runtime readback, plus at least one invalid-source path that proves no unintended state change.

## Reporting rule

Report exact counts for each layer. If backend lifecycle chains pass but the UI only exposes intake/research, say so explicitly: the product is not allowed to inherit frontend coverage from backend tests.

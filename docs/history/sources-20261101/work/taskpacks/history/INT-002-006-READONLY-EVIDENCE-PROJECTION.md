# INT-002..006 — Read-only evidence projection cross-task card

## Scope

This card authorizes one cross-module, read-only vertical slice for WORK-LAB:

```text
Workflow Evidence Envelope only
    -> Observer-owned normalized events
    -> project-local persistent projection/readback
```

## Allowed changes

- `30-observer/work-lab-observer/src/observer_evidence.py`
- `30-observer/work-lab-observer/tests/test_observer_evidence.py`
- `30-observer/work-lab-observer/README.md`
- this task card

## Allowed source contracts

- `10-workflow/workflow-assistance/schemas/workflow/evidence-envelope.schema.json`
- Open Design benchmark events are no longer a WORK-LAB input after the module transfer.

## Forbidden actions

- no Workflow Ledger mutation;
- no Open Design Registry mutation;
- no approval or promotion;
- no Git/GitHub mutation;
- no Hermes live configuration or provider/session access;
- no credentials, prompt/response bodies, auth stores or private source material;
- no external network calls.

## Acceptance

1. Valid Workflow evidence envelopes become Observer events without copying payloads.
2. Source content is represented by deterministic SHA-256 only.
3. Malformed, sensitive, unapproved or unsupported inputs fail closed.
4. Events persist through `ObserverStore` and rebuild after restart.
5. Existing module and root gates remain green.

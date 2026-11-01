# MiniMax Design host adapter — rights and provider policy

- **Task**: DL-P0-060
- **Status**: declaration only; no runtime, no API, no artifact
- **Related but separate**: `integrations/generators/minimax-h3/rights-and-provider-policy.md`

## Rights

- **Application terms are unread.** The manifest records
  `license: "unverified"`. No authorisation is inferred from the application
  being installed, licensed to the owner, or present in a subscription.
- **Model weights are a different question.** MiniMax H3 has its own licence
  record and its own fail-closed rule; see
  H3 许可证据交接（2026-09-13；原件已按 owner 2026-10-19 指令删除，其结论与独有事实汇总在 `docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md`，逐份 blob/restoreAt 在 `docs/history/archive-2026-10-19/REMOVALS.json`）. Accepting the
  application never accepts the weights.
- **Output rights are not claimed.** DESIGN-LAB asserts no rights over whatever
  the host produces. Any client delivery of host output requires its own
  delivery-side rights record.
- **No vendoring.** No host binary, asset library, template pack or model weight
  is copied into this repository.
- **No private-state reading.** The host's private databases, account state and
  personal asset library are outside the boundary, including read-only peeks for
  "diagnostics".

## Provider policy

- **No default host.** The product manifest declares no default host, and this
  adapter never becomes one.
- **Process isolation.** A live run, if authorised, happens in an isolated
  process and does not mutate shared host configuration.
- **No credential handling.** No API key, token or session cookie is read,
  stored, logged or forwarded. If the host needs a credential, the owner supplies
  it interactively.
- **No silent fallback.** If the host cannot perform an operation, the adapter
  reports it as unsupported rather than routing the work to another tool and
  reporting the host's name on the result.
- **No cost or rate-limit invention.** Any hosted or metered behaviour follows
  the official terms; the adapter does not impose undisclosed limits.

## Boundary

- Runtime, cache and temporary files belong under `.project-local/task-runtime/`;
  evidence belongs under `.project-local/task-artifacts/`; persistent artifacts
  go through the asset service.
- `E:\` is never accessed.
- No shared runtime state is touched.

## Promotion conditions (E0 → E2/E3)

1. Owner authorisation for the window, with scope and date.
2. An adjudicated rights position for the application terms.
3. A user-approved host profile.
4. The POC plan executed with artifact digest, readback digest, failure/recovery
   and rollback recorded.
5. A human gate signature — an agent may prepare the record but may not sign it.

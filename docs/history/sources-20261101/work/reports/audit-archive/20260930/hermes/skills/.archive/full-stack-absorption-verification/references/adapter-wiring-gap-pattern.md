# Adapter wiring gap pattern

**Registered adapters never wired into the product engine chain.**

## The pattern

1. Adapter registry is populated (e.g. via `register_adapter()` calls during `ensure_registered()`).
2. Each adapter has its own test class (fixture tests, contract tests, edge-case tests) — all green in isolation.
3. The product's actual ingestion/format-dispatch pipeline (`_ENGINES` dict, handler map, route table, or provider chain) only references a subset of those registered adapters.
4. The unbundled adapters compile and pass their unit tests, but the product never invokes them.

## How this happens

- Registry population and engine-chain population are separate code paths that must be manually kept in sync.
- A developer adds an adapter (registers it, writes tests) but forgets to add it to the product's routing table.
- The adapter tests pass because they call the adapter function directly (e.g. `convert_pillow(inp)`) — not through the product's format-dispatch function.
- No integration or E2E test exercises the product boundary for the new format/kind.

## Detection

```python
# Get full registry
reg = get_adapter_registry()
print(f"Registry entries: {len(reg)}")
for k in sorted(reg):
    print(f"  {k}")

# Get engine-chain entries
print(f"Engine chain entries: {len(_ENGINES)}")
for fmt, chain in _ENGINES.items():
    print(f"  {fmt}: {[e[0] for e in chain]}")

# Cross-reference
from shared.adapter_contract import AdapterKind
registered_kinds = {v.kind for v in reg.values()}
engine_kinds = set()
for fmt, chain in _ENGINES.items():
    engine_kinds.add(fmt)
print(f"Registered kinds without engine entry: {registered_kinds - engine_kinds}")
```

## Impact

- Features claimed as "implemented" (test evidence exists) are not reachable by the product.
- A user interacting with the product through its API or UI will never see the adapter's output.
- Release manifests quantifying "N adapters" will be inflated relative to actual product capability.

## Fix

Add an entry for the missing format/kind to the product's engine chain. For registry-based dispatchers, add the kind string or format key to the routing table. Add at least one integration test that calls the product's boundary function (e.g. `convert_file(path)`) with a fixture of the new format and asserts the engine name matches the new adapter.

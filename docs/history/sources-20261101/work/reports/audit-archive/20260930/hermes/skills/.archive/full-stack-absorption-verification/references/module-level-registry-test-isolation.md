# Module-level registry test isolation

## Problem

A global `_ADAPTER_REGISTRY` (or similar module-level dict) populated at import time by `ensure_registered()`. The `ensure_registered()` function uses a `_registered` flag to run registration only once:

```python
_registered = False

def ensure_registered() -> None:
    global _registered
    if not _registered:
        _register_all()
        _registered = True
```

An isolated test class calls `mod._ADAPTER_REGISTRY.clear()` in its `setup_method` to start with a clean slate. Subsequent tests in a *different* class call `ensure_registered()` expecting the registry to be populated, but the `_registered` flag is already `True` — so `_register_all()` is skipped and the registry stays empty. Tests fail with `assert 0 >= 2` or similar.

This only appears when running the full test suite (class C1 clears → class C2 silently no-ops), not when running C2 alone (where `ensure_registered()` runs for the first time during import).

## Fix

Make `ensure_registered()` resilient to external clearing by checking the actual registry state when `_registered` is `True`:

```python
def ensure_registered() -> None:
    global _registered
    if _registered:
        from shared.adapter_contract import get_adapter_registry
        if get_adapter_registry():
            return  # already populated
    _register_all()
    _registered = True
```

This adds one `if` + dict-lookup overhead on every subsequent call, but is negligible compared to the registration cost itself. The `_registered` guard still avoids re-importing heavy deps when the registry is healthy.

## Prevention

For new code, **don't clear a global registry in `setup_method()`**. Use per-test fixtures or a dedicated test helper that shadows the registry with a dict argument instead of mutating the shared state. When you must test registry isolation, create a fresh registry instance and pass it explicitly rather than clearing a module-level singleton whose consumers use a cached flag.

## Detection

When you see `assert 0 >= N`, `assert None is not None` (from `lookup_adapter()` returning None), or `assert len(X) >= N` with `len(X) == 0` in registry-population tests that call `ensure_registered()` or equivalent, suspect the cached-flag + external-clear race. Temporarily add `print(f"_registered={_registered}, registry_size={len(get_adapter_registry())}")` at the start of `ensure_registered()` to confirm.

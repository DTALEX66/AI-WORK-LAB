# Rollback-safe nested gameplay state

Use this pattern when adding a gameplay subsystem to a state tree that already supports snapshots, revive, rewind, save/load, or replay.

## Vertical slice

1. Read the actual snapshot and restore implementation before choosing the new state shape.
2. Add a failing test for a fresh initial baseline and object isolation across two initializations.
3. Add a failing end-to-end rollback test with realistically nested data: active rules, current shift/event with nested evidence, tool charges/resources, and discovered evidence.
4. Save a snapshot, mutate the live state with post-snapshot data, then restore.
5. Assert that post-snapshot mutations are absent from the restored state.
6. Mutate the restored state and assert that snapshot history remains unchanged.
7. Implement the smallest initialization change, preferably by reusing the subsystem's existing state factory.
8. Run subsystem, state, and generated-bundle execution tests before full platform gates.

## Recommended state boundary

Keep session scheduling and per-shift investigation distinct:

```js
{
  night: {
    activeProtocols: [],
    currentShift: null,
    roundType: 'quick',
    shiftIndex: 0,
    decisions: [],
    eventChains: {},
    nextShiftModifiers: [],
  },
  investigation: createInvestigationState({ power: initialPower }),
}
```

This makes later scheduling explicit without duplicating tool initialization.

## Acceptance and pitfall

A JSON-based clone is sufficient only for JSON-safe values. If factories include `Infinity`, functions, class instances, Maps/Sets, typed arrays, or undefined-bearing records, test serialization explicitly and use a compatible clone strategy. `JSON.stringify` converts `Infinity` to `null`; an unlimited-charge tool therefore needs a JSON-safe representation or restore-time normalization before it becomes persisted gameplay state.

Generated platform bundles are tracked artifacts in some repositories. Rebuild and explicitly stage them only after bundle execution tests prove dependency order and exports work.
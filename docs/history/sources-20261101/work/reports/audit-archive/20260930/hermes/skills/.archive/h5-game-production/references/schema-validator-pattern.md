# Self-Contained Schema Validator Pattern

When JSON data needs structural validation (skins, configs, content packs), write a self-contained walker instead of pulling in `ajv` or other npm deps. This keeps `npm install` optional and CI lightweight.

## Structure

```
schemas/<thing>.schema.json   ← JSON Schema (draft-07 subset)
scripts/validate-<thing>.mjs  ← validator (no deps)
package.json                  ← `npm run <thing>:check`
```

## Validator Skeleton

```js
#!/usr/bin/env node
// validate-<thing>.mjs — lightweight schema walker. No npm deps.

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const schemaPath = resolve(root, 'schemas', '<thing>.schema.json');
let failures = 0;

function fail(msg) { process.stderr.write(`[schema] FAIL: ${msg}\n`); failures++; }
function pass(msg) { process.stdout.write(`[schema] PASS: ${msg}\n`); }

// Recursive schema walker — handles object, array, string, integer, multi-type
function validate(instance, subschema, path) {
  if (subschema.type === 'object') {
    if (typeof instance !== 'object' || instance === null || Array.isArray(instance)) {
      fail(`${path}: expected object, got ${typeof instance}`); return;
    }
    if (subschema.required) {
      for (const key of subschema.required) {
        if (!(key in instance)) fail(`${path}: missing required key "${key}"`);
      }
    }
    if (subschema.minProperties !== undefined) {
      if (Object.keys(instance).length < subschema.minProperties) {
        fail(`${path}: expected >= ${subschema.minProperties} properties`);
      }
    }
    // recurse into properties + additionalProperties
  } else if (subschema.type === 'array') { /* minItems + items walk */ }
  else if (Array.isArray(subschema.type)) { /* multi-type: ["integer","string"] */ }
  else if (subschema.type === 'string') { /* minLength */ }
  else if (subschema.type === 'integer') { /* minimum/maximum */ }
}

// Discover data files, validate each, exit 1 on any failure
```

## Pitfalls

1. **Shebang + block comments on Windows ESM.** `#!/usr/bin/env node` followed by `/* ... */` can cause parse errors in Node ESM mode. Use `//` line comments instead.
2. **Data shape before schema shape.** Read the actual JSON files first. Hidden logs may be keyed objects, not arrays. Effect fields like `floor` may be strings (`"+4"`) rather than integers.
3. **Multi-type fields.** Use `"type": ["integer", "string"]` in JSON Schema and check `Array.isArray(subschema.type)` in the validator walker.
4. **Cross-reference checks.** Beyond structural validation, assert that anomaly IDs match hidden log IDs 1:1.

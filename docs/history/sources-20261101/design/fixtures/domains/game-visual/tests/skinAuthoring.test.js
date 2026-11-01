import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const templatePath = resolve(root, 'templates/skin-template.json');
const guidePath = resolve(root, 'docs/SKIN_AUTHORING_GUIDE.md');
const schemaPath = resolve(root, 'schemas/skin.schema.json');
const pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8'));

function validate(instance, subschema, path = '$', failures = []) {
  const allowedTypes = Array.isArray(subschema.type) ? subschema.type : [subschema.type];
  if (allowedTypes.includes('object')) {
    if (typeof instance !== 'object' || instance === null || Array.isArray(instance)) {
      failures.push(`${path}: expected object`);
      return failures;
    }
    for (const key of subschema.required || []) {
      if (!(key in instance)) failures.push(`${path}: missing ${key}`);
    }
    for (const [key, propSchema] of Object.entries(subschema.properties || {})) {
      if (key in instance) validate(instance[key], propSchema, `${path}.${key}`, failures);
    }
    if (subschema.minProperties !== undefined && Object.keys(instance).length < subschema.minProperties) {
      failures.push(`${path}: expected at least ${subschema.minProperties} properties`);
    }
  } else if (allowedTypes.includes('array')) {
    if (!Array.isArray(instance)) {
      failures.push(`${path}: expected array`);
      return failures;
    }
    if (subschema.minItems !== undefined && instance.length < subschema.minItems) {
      failures.push(`${path}: expected at least ${subschema.minItems} items`);
    }
    for (let i = 0; i < instance.length; i++) {
      validate(instance[i], subschema.items || {}, `${path}[${i}]`, failures);
    }
  } else if (allowedTypes.includes('integer') && typeof instance === 'number') {
    if (!Number.isInteger(instance)) failures.push(`${path}: expected integer`);
  } else if (allowedTypes.includes('string')) {
    if (typeof instance !== 'string') failures.push(`${path}: expected string`);
    if (subschema.minLength !== undefined && typeof instance === 'string' && instance.length < subschema.minLength) {
      failures.push(`${path}: too short`);
    }
  } else if (allowedTypes.includes('integer')) {
    if (!(typeof instance === 'number' && Number.isInteger(instance))) failures.push(`${path}: expected integer`);
  }
  return failures;
}

test('skin authoring template is valid JSON and satisfies the skin schema', () => {
  const template = JSON.parse(readFileSync(templatePath, 'utf8'));
  const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));
  const failures = validate(template, schema);

  assert.deepEqual(failures, []);
  assert.equal(template.meta.id, 'skin-template');
  assert.ok(template.anomalies.length >= 12);
  for (const anomaly of template.anomalies) {
    assert.ok(template.hiddenLogs[anomaly.id], `${anomaly.id} should have a matching hidden log`);
  }
});

test('skin authoring guide documents the repeatable production workflow', () => {
  const guide = readFileSync(guidePath, 'utf8');

  for (const required of [
    'templates/skin-template.json',
    'src/skins/<skin-id>/skin.json',
    'npm run skins:check',
    'npm test',
    'node build.js wechat',
    'meta.id',
    'actionLabels',
    'canvasLabels',
    'anomalies',
    'hiddenLogs',
    '12',
    '地铁末班调度室',
  ]) {
    assert.match(guide, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('skin:new creates a new skin from the template without overwriting existing skins', () => {
  const skinId = 'autogen_test_skin';
  const skinName = '自动生成测试皮肤';
  const skinDir = resolve(root, 'src/skins', skinId);
  const skinPath = resolve(skinDir, 'skin.json');

  assert.equal(pkg.scripts['skin:new'], 'node scripts/create-skin-from-template.mjs');
  rmSync(skinDir, { recursive: true, force: true });

  try {
    const output = execFileSync(process.execPath, ['scripts/create-skin-from-template.mjs', skinId, skinName], {
      cwd: root,
      encoding: 'utf8',
    });
    assert.match(output, /created/i);
    assert.ok(existsSync(skinPath));

    const generated = JSON.parse(readFileSync(skinPath, 'utf8'));
    assert.equal(generated.meta.id, skinId);
    assert.equal(generated.meta.name, skinName);
    assert.equal(generated.meta.subtitle, 'MINIGAME · ANOMALY SYSTEM SIM');
    assert.ok(generated.anomalies.length >= 12);

    assert.throws(() => execFileSync(process.execPath, ['scripts/create-skin-from-template.mjs', skinId], {
      cwd: root,
      encoding: 'utf8',
      stdio: 'pipe',
    }), /already exists|Command failed/);
  } finally {
    rmSync(skinDir, { recursive: true, force: true });
  }
});

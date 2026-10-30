// SPDX-License-Identifier: MIT
// DESIGN-LAB Workbench — shape-notice coverage gate.
//
// `apiOrEmpty` is the one seam that turns a reachable-but-short service answer into a
// renderable payload. When it has to invent a collection, the view must SAY SO
// (`未读回：响应缺少 X`) instead of letting a synthetic empty read as "the project has
// none". That rule is trivially lost: adding a new seam read, or renaming its variable,
// silently removes one view's honesty with no type error and no failing render.
//
// So this gate walks the real TypeScript AST of shell.ts and asserts, per binding:
//   * every value produced by an `apiOrEmpty` call is named in a `shapeNotice` /
//     `shapeNoticeRows` call inside the same enclosing function; and
//   * every `apiOrEmpty` call site binds a name this file can see (an unbound
//     `await apiOrEmpty(...)` whose result nothing reads is a hole, not a pass).
//
// Names are matched identifier-by-identifier, so dropping one argument from one notice
// call fails this gate. Parsing with the compiler rather than regexes: braces, template
// literals and comments in shell.ts are not things a line pattern can be trusted about.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const sourcePath = join(here, '..', 'shell.ts');
const text = readFileSync(sourcePath, 'utf8');
const source = ts.createSourceFile('shell.ts', text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);

let failures = 0;
const fail = (msg) => { failures += 1; console.error(`FAIL: ${msg}`); };
const pass = (msg) => console.log(`ok: ${msg}`);

const lineOf = (node) => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;

function isCallTo(node, name) {
  return ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === name;
}

// --- the seam must exist, or every assertion below is vacuously true -----------------
const seamDecls = [];
const noticeCalls = [];
(function findDeclarations(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === 'apiOrEmpty') seamDecls.push(node);
  if (isCallTo(node, 'shapeNotice') || isCallTo(node, 'shapeNoticeRows')) noticeCalls.push(node);
  node.forEachChild(findDeclarations);
})(source);

if (seamDecls.length !== 1) {
  fail(`expected exactly 1 'function apiOrEmpty' in shell.ts, found ${seamDecls.length} — the gate's subject moved`);
  console.log(failures > 0 ? `shape-notice coverage: ${failures} failure(s)` : 'shape-notice coverage: all bindings reported');
  process.exit(1);
}
if (!noticeCalls.length) {
  fail('no shapeNotice/shapeNoticeRows call survives in shell.ts — the notice feature was removed, not the gap');
  process.exit(1);
}

// --- enclosing function, for every node ---------------------------------------------
const enclosingFn = new Map();
(function mark(node) {
  if (ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) || ts.isArrowFunction(node)) {
    enclosingFn.set(node, node);
  }
  node.forEachChild((child) => mark(child));
})(source);

function nearestFunction(node) {
  let current = node.parent;
  while (current) {
    if (enclosingFn.has(current)) return current;
    current = current.parent;
  }
  return null;
}

function functionName(node) {
  if (!node) return '(module scope)';
  if (ts.isFunctionDeclaration(node) && node.name) return node.name.text;
  if (ts.isVariableDeclaration(node.parent) && ts.isIdentifier(node.parent.name)) return node.parent.name.text;
  // An arrow handed to another function (the project-picker bodies) has no name of its
  // own; label it by the view it belongs to, so a failure points at a page.
  let current = nearestFunction(node.parent);
  while (current && !(ts.isFunctionDeclaration(current) && current.name)) current = nearestFunction(current.parent);
  return `(anonymous fn in ${current?.name?.text ?? 'module scope'})`;
}

// --- names covered by notice calls, per function ------------------------------------
const covered = new Map();
for (const call of noticeCalls) {
  const owner = nearestFunction(call);
  if (!covered.has(owner)) covered.set(owner, new Set());
  const set = covered.get(owner);
  for (const arg of call.arguments) {
    if (ts.isIdentifier(arg)) set.add(arg.text);
    else if (ts.isPropertyAccessExpression(arg) && ts.isIdentifier(arg.expression)) set.add(arg.expression.text);
  }
}

// --- names bound by each seam call --------------------------------------------------
function boundNames(call) {
  // const X = apiOrEmpty(...) | const X = await apiOrEmpty(...)
  let node = call;
  if (node.parent && ts.isAwaitExpression(node.parent)) node = node.parent;
  const parent = node.parent;

  if (parent && ts.isVariableDeclaration(parent) && ts.isIdentifier(parent.name)) {
    return [parent.name.text];
  }

  // const [a, b] = await Promise.all([apiOrEmpty(...), apiOrEmpty(...)])
  // Note where the `await` sits: it wraps the Promise.all CALL, so the ascent past it
  // has to happen after that call is recognised, not between it and the array literal.
  if (parent && ts.isArrayLiteralExpression(parent)) {
    let all = parent.parent;
    if (all && ts.isCallExpression(all) && ts.isPropertyAccessExpression(all.expression)
        && all.expression.name.text === 'all'
        && ts.isIdentifier(all.expression.expression)
        && all.expression.expression.text === 'Promise') {
      let decl = all.parent;
      if (decl && ts.isAwaitExpression(decl)) decl = decl.parent;
      if (decl && ts.isVariableDeclaration(decl) && ts.isArrayBindingPattern(decl.name)) {
        const index = parent.elements.indexOf(call);
        const element = decl.name.elements[index];
        if (element && ts.isBindingElement(element) && ts.isIdentifier(element.name)) {
          return [element.name.text];
        }
      }
    }
    return [];
  }
  return [];
}

// --- assert --------------------------------------------------------------------------
const sites = [];
(function walk(node) {
  if (isCallTo(node, 'apiOrEmpty')) sites.push(node);
  node.forEachChild(walk);
})(source);

if (!sites.length) fail('no apiOrEmpty call site found — the seam has no consumer, so this gate proves nothing');

const reported = [];
for (const call of sites) {
  const owner = nearestFunction(call);
  const names = boundNames(call);
  const label = `${functionName(owner)}@${lineOf(call)}`;
  if (!names.length) {
    fail(`${label}: an apiOrEmpty result is not bound to a readable name — the gate cannot prove it is reported`);
    continue;
  }
  const set = covered.get(owner) ?? new Set();
  const missing = names.filter((n) => !set.has(n));
  if (missing.length) {
    fail(`${label}: ${missing.join(', ')} read through apiOrEmpty but no shapeNotice call reports its missing fields`);
  }
  reported.push(`${label} -> ${names.join(',')}`);
}

if (failures === 0) {
  pass(`${sites.length} seam read(s), every bound value reported: ${reported.join(' | ')}`);
}

console.log(failures > 0 ? `shape-notice coverage: ${failures} failure(s)` : 'shape-notice coverage: all bindings reported');
process.exit(failures > 0 ? 1 : 0);

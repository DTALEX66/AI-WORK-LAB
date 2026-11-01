/* WORK-LAB Observer — tests/run_all_tests.js
   Runs every test_*.js suite and reports a combined pass/fail exit code. */

"use strict";

const suites = [
  // U03 (2026-10-07): the five static-surface suites and the helpers.js that read
  // apps/observer/web were retired with that tree. Their guarantees live on the
  // production side now — see docs/audits/OBSERVER_WEB_RETIREMENT_MANIFEST_2026-10-07.json
  // and apps/observer/parity-matrix-u03.md for the per-assertion attribution.
  "./test_desktop_component_contract.js",
  "./test_production_surface_static_contract.js",
];

async function main() {
  let totalPass = 0, totalFail = 0;

  for (const s of suites) {
    const mod = require(s);
    const result = await mod.run();
    totalPass += result.pass;
    totalFail += result.fail;
  }

  console.log(`\n==== WORK-LAB Observer UI contract tests ====`);
  console.log(`TOTAL: ${totalPass} passed, ${totalFail} failed`);
  return totalFail ? 1 : 0;
}

main().then(
  (code) => { process.exitCode = code; },
  (err) => {
    console.error(err);
    process.exitCode = 1;
  }
);

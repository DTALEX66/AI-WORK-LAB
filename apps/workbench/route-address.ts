// SPDX-License-Identifier: MIT
// DESIGN-LAB Workbench - route address helpers (D07 split, batch 1).
//
// Pure string <-> hash mapping for the parameterized detail routes. No DOM, no service
// read, no module state: every function here is a total function of its arguments, which
// is exactly what lets the route table and the palette share one address vocabulary
// without sharing a module with the screens that render them.
//
// `#/...` addresses are the router's only input: every jump in shell.ts is a
// `window.location.hash` assignment, so a condition has to travel in the hash.

const PROJECT_DETAIL_RE = /^#\/projects\/([^/?#]+)$/;
// Project ids are `uuid4().hex` service-side. Validating the DECODED value is
// what closes the hole: the regex above admits `%`, so `#/projects/%2e%2e%2f…`
// decoded into a string containing `/` and `?` and was interpolated straight
// into API paths. Bare `%` also made decodeURIComponent throw, which aborted
// the whole route render.
const PROJECT_ID_RE = /^[0-9a-f]{32}$/;

/** Project id from a `#/projects/<id>` hash, or null for any other hash. */
export function projectDetailId(hash: string): string | null {
  const m = PROJECT_DETAIL_RE.exec(hash);
  if (!m || !m[1]) return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(m[1]);
  } catch {
    return null;
  }
  return PROJECT_ID_RE.test(decoded) ? decoded : null;
}

/** Hash for the project-detail route (B07 `/projects/:id`). */
export function projectDetailHash(id: string): string {
  return '#/projects/' + encodeURIComponent(id);
}

// DL-UI-U03 (R2 §5): a capability's full detail must be re-findable, so it gets its own
// address the same way a project does. Same hardening as above -- validate the DECODED
// id, because the shape regex admits `%`. Measured charset of the 60 recorded ids is
// `[a-z0-9-]`, longest 27; anything else (traversal, encoded slash, bare `%`) resolves to
// "no such route" rather than reaching the payload lookup.
// DETAIL_ID_RE is shared with the domain-pack detail address below: both identities are
// repo-declared lower slugs, and one validated shape is one less place to drift.
const CAPABILITY_DETAIL_RE = /^#\/capabilities\/([^/?#]+)$/;
const DETAIL_ID_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;

/** Capability id from a `#/capabilities/<id>` hash, or null for any other hash. */
export function capabilityDetailId(hash: string): string | null {
  const m = CAPABILITY_DETAIL_RE.exec(hash);
  if (!m || !m[1]) return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(m[1]);
  } catch {
    return null;
  }
  return DETAIL_ID_RE.test(decoded) ? decoded : null;
}

/** Hash for one capability's detail address. */
export function capabilityDetailHash(id: string): string {
  return '#/capabilities/' + encodeURIComponent(id);
}

// R2 §2 — the domain packs are second-level entries, so one pack needs its own address
// the same way one capability does. `packId` (not `directory`) is the stable identity a
// manifest declares, so it is what travels in the hash; a pack whose manifest declares
// no pack_id has no addressable detail and stays in the list.
const DOMAIN_DETAIL_RE = /^#\/domains\/([^/?#]+)$/;

/** Pack id from a `#/domains/<packId>` hash, or null for any other hash. */
export function domainDetailId(hash: string): string | null {
  const m = DOMAIN_DETAIL_RE.exec(hash);
  if (!m || !m[1]) return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(m[1]);
  } catch {
    return null;
  }
  return DETAIL_ID_RE.test(decoded) ? decoded : null;
}

/** Hash for one domain pack's detail address, or null when the pack declares no id. */
export function domainDetailHash(packId: string | null | undefined): string | null {
  return packId ? '#/domains/' + encodeURIComponent(packId) : null;
}

// R2 §2 → §4: opening one pack and asking "which capabilities declare this domain" is a
// *conditional* address, not a bare one. The condition travels **in the hash**, after a `?`,
// because every jump in this file is `window.location.hash = …` and that assignment is what
// fires the router; a condition parked in `location.search` would rewrite the address without
// ever re-rendering the view. `hashPath` is therefore what the route table matches against,
// and the route table still matches `#/capabilities` exactly -- one address, one condition.
const HASH_SPLIT_RE = /^([^?]*)(?:\?(.*))?$/g;
/** The path part of a hash, with any `?...` condition removed. */
export function hashPath(hash: string): string {
  const m = HASH_SPLIT_RE.exec(hash);
  HASH_SPLIT_RE.lastIndex = 0;
  return m ? m[1] : hash;
}
/** One condition value from a hash's `?...` part, or null when it is absent. */
export function hashCondition(hash: string, name: string): string | null {
  const m = HASH_SPLIT_RE.exec(hash);
  HASH_SPLIT_RE.lastIndex = 0;
  const query = m && m[2];
  if (!query) return null;
  for (const pair of query.split('&')) {
    const eq = pair.indexOf('=');
    if (eq <= 0 || pair.slice(0, eq) !== name) continue;
    try {
      const value = decodeURIComponent(pair.slice(eq + 1));
      return value || null;
    } catch {
      return null;                      // a malformed escape is no condition, not a crash
    }
  }
  return null;
}
/**
 * The capability-library address carrying one declared domain.
 *
 * A slug that is not a non-empty string yields the bare address: a pack that declares no
 * domain must land on the unfiltered list rather than on a condition that matches nothing
 * for a reason the reader cannot see.
 */
export function capabilityHashForDomain(slug: string | null | undefined): string {
  return slug ? '#/capabilities?domain=' + encodeURIComponent(slug) : '#/capabilities';
}

/** The `axes.domains` a capability record declares, as strings. */
export function declaredDomains(row: { axes?: { domains?: unknown } } | null | undefined): string[] {
  const values = row?.axes?.domains;
  return Array.isArray(values)
    ? values.filter((value): value is string => typeof value === 'string')
    : [];
}
/** True when the record itself says its `domains` axis was never classified. */
export function domainsUnclassified(row: { unclassifiedAxes?: unknown } | null | undefined): boolean {
  const axes = row?.unclassifiedAxes;
  return Array.isArray(axes) && axes.includes('domains');
}

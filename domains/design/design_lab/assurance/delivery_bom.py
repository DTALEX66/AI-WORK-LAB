# SPDX-License-Identifier: MIT
"""Build the delivery BOM the declared contract describes, or refuse and name what is missing.

Until this module existed the only thing in the product named ``bom`` was the fragment
``{'items': [{'id', 'path', 'sha256'}]}`` that ``assurance/production_preflight.py`` assembled from a
bundle manifest to answer its own link check -- renamed on 2026-10-08 to ``link_manifest`` precisely
because it is not a bill of materials. That fragment is not the declared document either:
``design-lab/schemas/bom.schema.json`` requires ``version``, ``handoff``, ``items[]`` with ``path``,
``kind``, ``format``, ``sha256``, ``source``, ``license``, and ``provenance`` with ``boundTreeSha``,
``generatedAt``, ``environment``, ``toolVersion``, ``inputHash`` -- every object closing extras with
``additionalProperties: false``. Running the fragment through that schema rejects it, which is how a
declared contract stays unfalsified for months: nobody executed the check the contract implies.

So the boundary is stated in code, and where the delivery path records nothing this module refuses
instead of inventing. What the bundle manifest does give:

* ``files[]`` -- member name (path), ``sha256``, ``role`` (primary / preview / input), which decides
  ``kind`` and, from the member suffix, ``format``;
* ``metadata`` -- the host and host version (``provenance.environment``), the job digest
  (``provenance.inputHash``), the registered input asset ids (item ``source`` for an input) and the
  rights state recorded at delivery (item ``license``).

What no stored artifact states, so a caller must attest it or :func:`build` declines: which handoff
document the bill belongs to, which repository tree the delivery was made from, and which tool
version produced it. A BOM that wrote ``unknown`` in those three places would validate and still
read as a bill of materials, which is the false green this file exists to prevent.
"""
from __future__ import annotations

from pathlib import Path
import re

from ..interop import load_schema, schema_errors
from ..runtime.state_resources import repo_resource

BOM_SCHEMA_PATH = repo_resource('schemas/bom.schema.json')

#: role as ``native_bundles`` records it -> the kind vocabulary the BOM contract allows.
KIND_BY_ROLE = {'primary': 'export', 'preview': 'derived', 'input': 'derived'}
_FORMAT = re.compile(r'^\.([A-Za-z0-9]{1,12})$')
#: An id that is not an SPDX license and not a review outcome is not a licence statement.
UNKNOWN_RIGHTS = 'NOT_REVIEWED'

#: The fields a caller has to attest because nothing stored states them. Keyed in the order a reader
#: would have to satisfy them; the reasons are what the preflight finding prints.
UNATTESTED = {
    'handoff': 'no handoff document is created by the delivery path, so nothing can name which '
               'handoff this bill belongs to',
    'repo_tree_sha': 'the bundle manifest records no repository tree, so provenance.boundTreeSha has '
                     'no source until the delivery writer records HEAD at export time',
    'tool_version': 'the manifest records the host and its version but no adapter tool version, so '
                    'provenance.toolVersion has no source',
    'generated_at': 'neither the manifest nor the preflight run records when the delivery was made, '
                    'so provenance.generatedAt has no source',
}


def bom_version() -> str:
    """The BOM document version, taken from the contract rather than typed in here."""
    schema = load_schema(BOM_SCHEMA_PATH)
    const = ((schema.get('properties') or {}).get('version') or {}).get('const')
    if not isinstance(const, str) or not const.strip():
        raise ValueError(f'{BOM_SCHEMA_PATH.name} declares no version const, so a document that '
                         'claims to be one cannot say which version it is')
    return const


def _format_of(name: str) -> str:
    match = _FORMAT.match(Path(name).suffix.lower())
    return match.group(1) if match else 'unknown'


def items(manifest: dict) -> list[dict]:
    """One bill line per manifest member, from the bytes the manifest actually records."""
    metadata = manifest.get('metadata') or {}
    source_by_member = {str(entry.get('member')): str(entry.get('id'))
                        for entry in (metadata.get('input_assets') or []) if isinstance(entry, dict)}
    attempt = str(metadata.get('native_attempt_id') or 'unrecorded-attempt')
    host = str(metadata.get('host') or 'unrecorded-host')
    rights = str(metadata.get('rights') or UNKNOWN_RIGHTS)
    bill = []
    for name, entry in sorted((manifest.get('files') or {}).items()):
        if not isinstance(entry, dict):
            continue
        role = str(entry.get('role') or 'derived')
        bill.append({
            'path': str(name),
            'kind': KIND_BY_ROLE.get(role, 'derived'),
            'format': _format_of(str(name)),
            'sha256': str(entry.get('sha256') or ''),
            # An input is billed against the registered asset it came from; anything the host
            # rendered is billed against the attempt and the host, because a member name says
            # nothing about provenance that a reader could act on.
            'source': (source_by_member.get(str(name)) or f'unregistered-input:{name}')
            if role == 'input' else f'native-attempt:{attempt}/{host}',
            'license': rights,
        })
    return bill


def build(*, manifest: dict, handoff: str | None = None, repo_tree_sha: str | None = None,
          tool_version: str | None = None, generated_at: str | None = None) -> dict:
    """The declared BOM for one delivered bundle, or the named reasons it cannot be written yet."""
    supplied = {'handoff': handoff, 'repo_tree_sha': repo_tree_sha,
                'tool_version': tool_version, 'generated_at': generated_at}
    missing = [field for field in UNATTESTED if not str(supplied[field] or '').strip()]
    bill = items(manifest)
    if not bill:
        missing.append('items')
    if missing:
        return {'status': 'DELIVERY_BOM_INCOMPLETE', 'missing': missing,
                'reasons': {field: UNATTESTED[field] for field in missing if field in UNATTESTED}
                | ({'items': 'the bundle manifest names no files, so there is no bill to write'}
                   if 'items' in missing else {}),
                'attested': sorted(set(UNATTESTED) - set(missing)),
                'note': 'refusing rather than filling an unattested field with a placeholder'}
    metadata = manifest.get('metadata') or {}
    document = {
        'version': bom_version(),
        'handoff': str(handoff).strip(),
        'generated_at': str(generated_at).strip(),
        'project': str(metadata.get('project_id') or ''),
        'items': bill,
        'provenance': {
            'boundTreeSha': str(repo_tree_sha).strip(),
            'generatedAt': str(generated_at).strip(),
            'environment': f"{metadata.get('host') or 'unrecorded-host'}"
                           f"/{metadata.get('host_version') or 'UNRECORDED'}",
            'toolVersion': str(tool_version).strip(),
            'inputHash': str(metadata.get('job_sha256') or ''),
        },
    }
    errors = schema_errors(load_schema(BOM_SCHEMA_PATH), document)
    if errors:
        return {'status': 'DELIVERY_BOM_REJECTED', 'errors': errors, 'bom': document}
    return {'status': 'DELIVERY_BOM', 'bom': document, 'version': document['version']}


def summary(result: dict) -> str:
    """One sentence a finding can carry, in the vocabulary the page already shows."""
    if result['status'] == 'DELIVERY_BOM':
        return (f"交付清单已按 {result['version']} 写成并通过合同：{len(result['bom']['items'])} 项")
    if result['status'] == 'DELIVERY_BOM_REJECTED':
        return '交付清单写成但未通过合同：' + '；'.join(result['errors'])
    return ('交付清单无法写成，尚无任何记录的字段：'
            + '、'.join(f"{field}（{result['reasons'][field]}）" for field in result['missing']))

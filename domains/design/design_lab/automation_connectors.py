# SPDX-License-Identifier: MIT
"""Read-only projection of the automation connectors this repository has REGISTERED.

This module reads committed records and nothing else: it never launches a host, never
opens a socket, never spawns a bridge process, and never calls a tool. That is the whole
point of its existence -- owner 2026-10-28 lifted the freeze on the external-software
automation capability class ("取消冻结的自动化任务"), and the first honest surface for it is
a screen that can say which connectors are known, which have ever been probed from this
project, and which are deliberately not enabled.

Two records feed it:

* ``integrations/adapter-registry.json`` -- the project's own 30 adapter rows;
* ``docs/history/record-archive-2026-10-28-design-automation/ARCHIVE-MANIFEST.json`` --
  the byte-registered delivery pack, whose ``connectors`` block was lifted out of the ZIP
  this manifest pins, so a clean checkout answers the same table from tracked bytes.

Three rules this projection keeps, because they are this project's recurring failure modes:

1. ``NOT_PROBED`` is the default and is not ``UNAVAILABLE``. Absence of a probe says nothing
   about the connector; the pack's own vocabulary (``MCP_READY`` / ``UNAVAILABLE``) comes from
   a tools/list try/except and never proves the host application is usable, so those words are
   reported as the pack's readings, never adopted as this project's verdict;
2. a record that cannot be read gets an explicit state and an empty list with a reason --
   never a silently empty table that reads as "no connectors exist";
3. the counts are derived in the call from the rows returned. ``tools_listed_total`` is the
   pack's evidence of listed tools, not a capability count, and it is published next to
   ``native_tool_calls_executed: 0`` so the two cannot be confused.
"""
from __future__ import annotations

import json
from pathlib import Path

from design_lab.runtime.state_resources import repo_resource

REGISTRY_REL = Path('integrations/adapter-registry.json')
PACK_REL = Path('docs/history/record-archive-2026-10-28-design-automation/ARCHIVE-MANIFEST.json')

#: Both inputs are repository-committed records, so an installed wheel has to carry them. Before
#: this module used `repo_resource`, it computed the repository root as `parents[2]` of itself --
#: which inside a wheel is the interpreter's own `Lib`, measured as
#: `registry_state=MISSING pack_state=MISSING connectors=0`. An empty table on this page is not a
#: mild degradation: it reads as "no connector is registered", which is a false statement about
#: the repo. The pyproject force-include lines named `automation projection inputs` are what make
#: the installed answer the committed one.
MEANING = ('已登记的自动化连接器清单。这一页只读被跟踪的登记记录：不启动宿主软件、不打开端口、'
           '不拉起桥接进程、不调用任何工具。')
UNPROBED_MEANS = ('NOT_PROBED＝本项目从未探测过它，不等于"不可用"。包里 MCP_READY/UNAVAILABLE '
                  '只是"握手并列工具"的结果，不能读成宿主软件可用。')

#: Registered in the delivery pack but explicitly kept off by owner 2026-10-28: desktop UI
#: automation is the controlled-UI-automation tier, and a host launch is a per-action Human
#: Gate decision, not a capability the page may offer as a button.
NOT_ACTIVATED_BY_OWNER = ('windows',)


def _resource(rel: Path, root: Path | None) -> tuple[Path | None, str]:
    """Where to open one committed record: a planted root first, else packaged-then-checkout.

    `root` exists because the absence tests plant their own tree; it is never inferred from the
    caller's working directory, which is the mistake `repo_resource` was written to prevent.
    """
    if root is not None:
        candidate = root / rel
        return (candidate, 'STAGED') if candidate.is_file() else (None, 'MISSING')
    try:
        return Path(repo_resource(str(rel), source_root=())), 'RESOLVED'
    except FileNotFoundError:
        return None, 'MISSING'


def _read_json(path: Path | None, state: str) -> tuple[dict | None, str]:
    if path is None:
        return None, state
    try:
        return json.loads(path.read_text(encoding='utf-8')), 'READ'
    except (OSError, ValueError):
        return None, 'UNREADABLE'


def build(root: Path | None = None) -> dict:
    registry, registry_state = _read_json(*_resource(REGISTRY_REL, root))
    pack, pack_state = _read_json(*_resource(PACK_REL, root))

    adapters = (registry or {}).get('adapters') or []
    # Token match on the project's own adapter ids. This says "a row of the same name is
    # registered here", not "this is the same upstream implementation" -- that identity has
    # not been adjudicated, and a boolean would have claimed it anyway.
    #
    # Rows this very registration added (adapter-delivery-*) are excluded: joining a
    # connector to its own row would make the field true for all eleven and tell a reader
    # nothing. Measured against the pre-existing rows: blender, photoshop and illustrator
    # have same-named adapters; sketchup, autocad, rhino, 3dsmaxMCP, indesign, revit,
    # grasshopper and windows have none.
    def same_named_adapters(ident: str) -> list[str]:
        token = str(ident).lower().removesuffix('mcp')
        return sorted(str(row.get('adapter_id', '')) for row in adapters
                      if token and not str(row.get('adapter_id', '')).startswith(
                          'adapter-delivery-')
                      and token in str(row.get('adapter_id', '')).lower())

    connector_block = (pack or {}).get('connectors') or {}
    rows = []
    for entry in connector_block.get('rows', []):
        ident = entry.get('id')
        listed = entry.get('tools_listed_in_pack_evidence')
        handshaked = bool(entry.get('handshaked_in_pack_evidence'))
        rows.append({
            'id': ident,
            'transport': entry.get('transport'),
            'handshaked_in_pack_evidence': handshaked,
            'tools_listed_in_pack_evidence': listed,
            'native_tool_called_in_pack_evidence': entry.get('native_tool_called'),
            'design_lab_state': 'NOT_PROBED',
            'design_lab_enabled': False,
            'activation': ('NOT_ACTIVATED_BY_OWNER' if ident in NOT_ACTIVATED_BY_OWNER
                           else 'NOT_REQUESTED'),
            'same_named_project_adapters': same_named_adapters(ident),
            'rights': 'UNADJUDICATED' if ident != 'windows' else 'OUT_OF_SCOPE_THIS_ROUND',
        })

    tools_total = sum(row['tools_listed_in_pack_evidence'] or 0 for row in rows)
    quarantine = (pack or {}).get('quarantine') or {}
    return {
        'meaning': MEANING,
        'unprobedMeans': UNPROBED_MEANS,
        'registry_state': registry_state,
        'pack_state': pack_state,
        'counts': {
            'connectors': len(rows),
            'handshaked_in_pack_evidence': sum(1 for row in rows
                                               if row['handshaked_in_pack_evidence']),
            'tools_listed_total_in_pack_evidence': tools_total,
            'native_tool_calls_executed': 0,
            'probed_by_design_lab': 0,
            'enabled': 0,
            'project_adapters': len(adapters),
        },
        'connectors': rows,
        'pack': {
            'zip_bytes': (pack or {}).get('zip', {}).get('bytes'),
            'zip_sha256': (pack or {}).get('zip', {}).get('sha256'),
            'declared_connections': connector_block.get('declared_connections'),
            'verification': (pack or {}).get('verification', {}).get('unlisted_in_zip')
            and {k: (pack or {}).get('verification', {}).get(k)
                 for k in ('matched', 'mismatch', 'missing')},
        },
        'not_activated': connector_block.get('not_activated', []),
        'inert_instruction_blobs': quarantine.get('instruction_bodies'),
        'evidence_ceiling': 'E1/E2',
        'claims_not_made': [
            '没有启动任何专业软件，也没有调用任何工具',
            '不把 543 条已列工具读成本项目已具备的能力数',
            '不声明真实宿主 E3、真人 E4 或 release',
            'windows 桌面 UI 自动化连接器未被启用，启用需要 owner 另给明确授权',
            '包内 SKILL.md 与 install 字样是惰性素材，不进入本项目的指令面或能力计数',
        ],
    }

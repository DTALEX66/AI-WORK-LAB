# SPDX-License-Identifier: MIT
"""The model catalogue the desktop picker reads: two registries, shown side by side, not merged.

Owner ruling 2026-10-20: 「大模型可以 但为什么要锁死呢？不锁死 做好菜单导航和接口
用户自行选择本地或者是云端模型」. An interface for choosing needs one honest document to choose from,
and the facts already exist in two places that do NOT share a key:

* ``design-lab/readiness/model-radar.json`` records candidate models (14 rows: family, where the
  weights are, what machine state was observed, licence position, hardware fit);
* ``design-lab/config/provider-capabilities.json`` records callable endpoints (9 rows, all
  ``local_first``, all evidence level E0).

They are returned as two sections with ``join.key = null`` and the reason, because inventing a
shared axis to make one tidy table would be this project's named failure mode: a join that the data
cannot support. ``design-lab/tests/test_model_catalog.py`` asserts the join stays unclaimed.

What this module never does: it promotes nothing. ``qualified_local``, ``weights_recorded`` and
``default_enabled_true`` are counted from the registry so the page cannot render a green "ready"
chip that the registry does not support; the radar's own fail-closed rule (only ``QUALIFIED_LOCAL``
with ``machine_state >= LOAD_VERIFIED`` and a non-zero recorded weight hash may default-enable) stays
where it is defined, in ``readiness/model_radar.py``. Choosing is recorded as an operator action and
changes no state in this repository -- there is no transport here (``knowledge_review`` answers
``outbound.transport = NOT_CONNECTED``), so the catalogue says so rather than letting a 选择 button
imply a call was made.
"""
from __future__ import annotations

import json
from pathlib import Path

from .readiness import ReadinessError
from .readiness.model_radar import load_registry
from .runtime.state_resources import repo_resource

CATALOG_VERSION = 'design-lab/model-catalog/v1'
PROVIDERS_PATH = repo_resource('config/provider-capabilities.json')

#: Placement words the page may show. `huggingface` and `vendor` are acquisition routes recorded by
#: the registry, not cloud inference endpoints: nothing here can claim a hosted model call is wired.
PLACEMENTS = ('local', 'huggingface', 'vendor')

SELECTION_RULES = (
    '模型不做锁定：选择面由操作者给出，本仓库不预设默认模型。',
    'fail-closed 的默认值不变：radar_state 不是 QUALIFIED_LOCAL、或权重摘要为空、或许可未裁定时，'
    'default_enabled 必须保持 false。',
    '操作者的选择是一次被记录的动作，不改变合格状态、不把 UNKNOWN 写成合格、不宣称推理已验证。',
    '本仓库没有任何发送通道（outbound.transport = NOT_CONNECTED），所以选择不会把素材送出本机。',
    '若选择云端：素材将离开本机，这是必须显式告知的后果，不是默认。',
)

CLAIMS_NOT_MADE = (
    'not a capability grant: a row here is a recorded candidate, not a qualified model',
    'no inference was run and no model was loaded to produce this document',
    'no licence was adjudicated; commercial_use values are copied from the registry',
    'no cloud transport exists, so no row is a callable hosted endpoint',
)


class ModelCatalogError(RuntimeError):
    """A registry the catalogue cannot report on. Fail closed; never render a partial list as empty."""


def _document(path: Path, label: str) -> dict:
    try:
        document = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ModelCatalogError(f'{label} cannot be read: {type(exc).__name__}: {exc}') from None
    if not isinstance(document, dict):
        raise ModelCatalogError(f'{label} must be a JSON object')
    return document


def _model(entry: dict) -> dict:
    source = entry.get('source') if isinstance(entry.get('source'), dict) else {}
    rights = entry.get('rights') if isinstance(entry.get('rights'), dict) else {}
    fit = entry.get('hardware_fit') if isinstance(entry.get('hardware_fit'), dict) else {}
    weights = entry.get('weights_sha256')
    hashes = weights if isinstance(weights, list) else []
    return {
        'model_id': entry.get('model_id'),
        'family': entry.get('family'),
        'placement': source.get('kind'),
        'source_ref': source.get('ref'),
        'radar_state': entry.get('radar_state'),
        'machine_state': entry.get('machine_state'),
        'hardware_fit': fit.get('verdict'),
        'vram_gib_required': fit.get('vram_gib_required'),
        'commercial_use': rights.get('commercial_use'),
        'license_id': rights.get('license_id'),
        'default_enabled': entry.get('default_enabled'),
        'weights_recorded': len(hashes),
        'blocking_reason': entry.get('blocking_reason'),
        'evidence_ref': entry.get('evidence_ref'),
    }


def catalog() -> dict:
    """Assemble the picker document from the two registries, counting what they actually hold."""
    try:
        radar = load_registry()
    except (ReadinessError, OSError, ValueError) as exc:
        raise ModelCatalogError(f'model radar registry refused to load: {exc}') from None
    providers = _document(PROVIDERS_PATH, 'provider capabilities')

    models = [_model(entry) for entry in radar.get('entries', []) if isinstance(entry, dict)]
    if not models:
        raise ModelCatalogError('the model radar carries no entries; an empty picker would read as '
                                '"no candidates exist" rather than "the registry is empty"')

    endpoints = [
        {'provider_id': row.get('provider_id'),
         'endpoint_ref': row.get('endpoint_ref'),
         'capabilities': row.get('capabilities'),
         'local_first': row.get('local_first'),
         'license': row.get('license'),
         'license_risk': row.get('license_risk'),
         'evidence_level': row.get('evidence_level'),
         'source': row.get('source')}
        for row in (providers.get('providers') or []) if isinstance(row, dict)
    ]

    return {
        'schemaVersion': CATALOG_VERSION,
        'observed_at': radar.get('observed_at'),
        'sources': {
            'models': 'design-lab/readiness/model-radar.json',
            'endpoints': 'design-lab/config/provider-capabilities.json',
        },
        'hardware': radar.get('hardware'),
        'policy': radar.get('policy'),
        'counts': {
            'models': len(models),
            'endpoints': len(endpoints),
            'qualified_local': sum(1 for row in models if row['radar_state'] == 'QUALIFIED_LOCAL'),
            'default_enabled_true': sum(1 for row in models if row['default_enabled'] is True),
            'weights_recorded': sum(1 for row in models if row['weights_recorded']),
            'placement': {kind: sum(1 for row in models if row['placement'] == kind)
                          for kind in PLACEMENTS},
        },
        'models': models,
        'endpoints': endpoints,
        'join': {'key': None,
                 'reason': 'model radar rows are keyed by model_id and provider-capabilities rows by '
                           'provider_id/endpoint_ref; no field is shared and no recorded mapping '
                           'exists, so merging them would fabricate the relationship. The page shows '
                           'both lists and never one joined table.'},
        'selection': {'mode': 'USER_CHOSEN_NOT_LOCKED', 'rules': list(SELECTION_RULES),
                      'transport': 'NOT_CONNECTED', 'executed': False},
        'claims_not_made': list(CLAIMS_NOT_MADE),
    }

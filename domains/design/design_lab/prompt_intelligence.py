# SPDX-License-Identifier: MIT
"""Prompt Intelligence: compose a visual prompt from stored records, and reverse-describe
one stored asset from observations a caller supplied.

This is the entry point the capability domain named in ``AUTHORITY.md`` and
``docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`` §3.3 was missing: before this module
the words "prompt" had zero occurrences in ``src/design_lab/http_service.py``, ``src/design_lab/cli.py``
and ``apps/workbench/shell.ts``, so the claim existed only as prose.

What it does, and does not, do:

* it reads what the project already recorded -- a Brief and a Direction written by
  ``design_layer.DesignLayer``, an asset's stored bytes and an explicit observation set lowered by
  ``asset_analysis.AssetAnalysis`` -- and assembles them into a prompt document. Every sentence in the
  output is either a verbatim stored field or a framing label this module owns;
* it performs **no inference about picture content**. It never guesses an audience, a mood, a palette
  or a subject that is not in a stored field: an absent field is reported in ``unknown`` with the reason
  it is absent, which is the difference between a prompt and a fabrication;
* it calls **no model**. ``model.executed`` is false in every document this module returns, and the
  ``model`` block is the slot the user's selection (``model_selection``) fills in when a person chooses
  a local or cloud model. Choosing does not make the output verified;
* reversal works from the caller's observations, because no local vision backend is qualified
  (``design-lab/readiness/model-radar.json``: ``QUALIFIED_LOCAL=0``, every entry
  ``default_enabled: false``). The text and geometry in a reversal are the caller's module's claims,
  carried with their confidence, never re-labelled as this product's observation.

Refusals are the product answer and keep their own codes: a superseded brief version, a direction that
belongs to another brief, no chosen direction, a target outside the radar families, or an empty
observation set. ``compose`` is deterministic -- same stored records, same target, same document id --
so a readback can be re-computed and compared, the way ``AssetAnalysis.derive`` pins ``timestamp``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .asset_analysis import AssetAnalysis, AssetAnalysisError
from .design_layer import DesignLayer, DesignLayerError
from .image_assets import ImageAssetError
from .interop import InteropError, load_schema, schema_errors
from .model_selection import ModelSelection
from .readiness import ReadinessError
from .readiness.model_radar import load_registry
from .runtime.state_resources import repo_resource

COMPOSITION_VERSION = 'design-lab/prompt-composition/v1'
REVERSAL_VERSION = 'design-lab/prompt-reversal/v1'
COMPOSITION_SCHEMA_PATH = repo_resource('schemas/prompt-composition-v1.schema.json')
REVERSAL_SCHEMA_PATH = repo_resource('schemas/prompt-reversal-v1.schema.json')

#: A composition id is `prompt-` + 32 hex; reversal is `reversal-` + 32 hex.
COMPOSITION_ID = re.compile(r'^prompt-[0-9a-f]{32}$')
REVERSAL_ID = re.compile(r'^reversal-[0-9a-f]{32}$')

#: Only these radar families describe a visual artifact a prompt can target. The family vocabulary is
#: READ FROM the radar registry rather than restated, so adding a family there is visible here and this
#: module does not become a second capability registry.
VISUAL_FAMILIES = ('image-generation', 'video-generation', '3d')

#: Fields the design-layer schema does not carry. They are always reported as unknown instead of
#: silently missing, because a reader of a prompt needs to know what the prompt does not say.
NOT_MODELLED = (
    {'field': 'audience', 'reason': 'design_brief stores goals and constraints, not an audience'},
    {'field': 'brand_assets', 'reason': 'no brand asset entity exists in the design layer'},
    {'field': 'copy_text', 'reason': 'no copy asset entity exists in the design layer'},
)

CLAIMS_NOT_MADE = (
    'no model ran: this text was assembled locally from stored records',
    'no visual judgement: nothing here ranks, scores or accepts the prompt',
    'no host call: no design software was asked to do anything with it',
    'no acceptance: composition is not a human or jury verdict',
)


class PromptIntelligenceError(Exception):
    """A refusal with the status code and machine-readable code the route will answer with."""

    def __init__(self, status, code, detail=None):
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail


def visual_families() -> tuple:
    """The target vocabulary, kept honest against the radar registry.

    Raises rather than falling back to the module constant when the radar file cannot be read: a
    silently defaulted vocabulary would accept a target that the registry has no family for.
    """
    try:
        document = load_registry()
    except (ReadinessError, OSError) as exc:
        raise PromptIntelligenceError(500, 'RADAR_REGISTRY_UNREADABLE',
                                      f'cannot read the model radar to validate a target: {exc}') from None
    families = {entry.get('family') for entry in document.get('entries', [])}
    return tuple(family for family in VISUAL_FAMILIES if family in families)


def _digest(parts) -> str:
    return hashlib.sha256('\x1e'.join(str(part) for part in parts).encode('utf-8')).hexdigest()[:32]


def _section(kind, text, source) -> dict:
    return {'kind': kind, 'text': text, 'source': source}


def check_document(document, schema_path, label):
    """Refuse to serve a prompt document that breaks its own contract.

    Every field is written by this module, so a mismatch is code and contract having diverged --
    a renamed key, a section whose source lost its digest, an `unknown` list that emptied out. The
    page would otherwise read a shortened prompt as a complete one, which is the failure this
    product is supposed to name rather than hide.
    """
    try:
        problems = schema_errors(load_schema(schema_path), document)
    except (InteropError, OSError) as exc:
        raise PromptIntelligenceError(
            500, f'{label.upper()}_CONTRACT_VIOLATION', [f'cannot load {schema_path.name}: {exc}']) from None
    if problems:
        raise PromptIntelligenceError(500, f'{label.upper()}_CONTRACT_VIOLATION', problems)
    return document


class PromptIntelligence:
    def __init__(self, service):
        self.service = service
        self.layer = DesignLayer(service)
        self.analysis = AssetAnalysis(service)
        self.selection = ModelSelection(service)

    # -- generation -------------------------------------------------------------

    def compose(self, project_id, *, brief_id, direction_id=None, target='image-generation'):
        """Assemble the prompt document for one live brief (and one live direction) at one target."""
        if target not in visual_families():
            raise PromptIntelligenceError(
                400, 'UNKNOWN_TARGET',
                f'target {target!r} is not a visual family in the model radar '
                f'({", ".join(visual_families())} are accepted)')
        brief = self._live_brief(project_id, brief_id)
        direction = self._live_direction(project_id, brief, direction_id)

        sources = {'brief': {'brief_id': brief['brief_id'], 'version': brief['version'],
                             'spec_sha256': brief['spec_sha256']},
                   'direction': ({'direction_id': direction['direction_id'],
                                  'version': direction['version'],
                                  'spec_sha256': direction['spec_sha256']}
                                 if direction else None)}

        sections = [_section('target', f'target: {target}',
                             {'kind': 'framing', 'rule': 'labelled by this module'})]
        sections.append(_section('subject', brief['title'],
                                 {'kind': 'stored', **sources['brief']}))
        for goal in brief['goals']:
            sections.append(_section('goal', goal, {'kind': 'stored', **sources['brief']}))
        if brief['constraints']:
            sections.append(_section('constraint', brief['constraints'],
                                     {'kind': 'stored', **sources['brief']}))
        if direction:
            sections.append(_section('stance', direction['title'],
                                     {'kind': 'stored', **sources['direction']}))
            for note in direction['style_notes'] or []:
                sections.append(_section('style', note, {'kind': 'stored', **sources['direction']}))
            if direction['color_mood']:
                sections.append(_section('colour', direction['color_mood'],
                                         {'kind': 'stored', **sources['direction']}))
            if direction['typography_mood']:
                sections.append(_section('typography', direction['typography_mood'],
                                         {'kind': 'stored', **sources['direction']}))

        prompt_text = '\n'.join(section['text'] for section in sections)
        # The operator's recorded choice is echoed, never inferred, and it does not make the
        # document model-generated: `executed` stays false because nothing here ran anything.
        selection = self.selection.readback(project_id)
        chosen = selection['selection'] if selection['state'] == 'CHOSEN' else None
        document = {
            'schemaVersion': COMPOSITION_VERSION,
            'composition_id': 'prompt-' + _digest([project_id, brief['brief_id'], brief['version'],
                                                   (direction or {}).get('direction_id', ''),
                                                   (direction or {}).get('version', ''),
                                                   target, prompt_text, selection['state'],
                                                   (chosen or {}).get('revision', '')]),
            'project_id': project_id,
            'target': target,
            'prompt_text': prompt_text,
            'sections': sections,
            'observed': [section['source'] for section in sections
                         if section['source'].get('kind') == 'stored'],
            'framing': [section['source'] for section in sections
                        if section['source'].get('kind') == 'framing'],
            'unknown': list(NOT_MODELLED),
            'model': {'selected': chosen, 'selection_state': selection['state'], 'executed': False},
            'claims_not_made': list(CLAIMS_NOT_MADE),
        }
        if direction is None:
            document['unknown'].append(
                {'field': 'direction',
                 'reason': 'no direction chosen under this brief, so the prompt carries the brief only'})
        return check_document(document, COMPOSITION_SCHEMA_PATH, 'composition')

    def _live_brief(self, project_id, brief_id):
        try:
            brief = self.layer.get_brief(project_id, brief_id)['brief']
        except DesignLayerError as exc:
            raise PromptIntelligenceError(exc.status, exc.code, exc.detail) from None
        if brief['superseded_by']:
            raise PromptIntelligenceError(
                409, 'STALE_REVISION',
                f'brief {brief_id} version {brief["version"]} was superseded by '
                f'{brief["superseded_by"]}; composing from a superseded brief would read as current intent')
        return brief

    def _live_direction(self, project_id, brief, direction_id):
        """Return the live direction to compose with, or None when the brief stands alone.

        An explicit ``direction_id`` is honoured only when it is this brief's own, un-superseded row:
        a direction from another brief would put one project's stance into another's prompt.
        """
        if direction_id is None:
            rows = [row for row in self.layer.list_directions(project_id)['directions']
                    if row['brief_id'] == brief['brief_id'] and row['chosen']]
            live = [row for row in rows if not row['superseded_by']]
            if len(live) == 1:
                return live[0]
            if rows and not live:
                # The human choice points at a version that has since been revised. Composing
                # without it would quietly drop a stance the project did choose, so it is named.
                raise PromptIntelligenceError(
                    409, 'STALE_REVISION',
                    f'the chosen direction {rows[0]["direction_id"]} was superseded by '
                    f'{rows[0]["superseded_by"]}; choose the new version before composing')
            return None
        try:
            direction = self.layer.get_direction(project_id, direction_id)['direction']
        except DesignLayerError as exc:
            raise PromptIntelligenceError(exc.status, exc.code, exc.detail) from None
        if direction['brief_id'] != brief['brief_id']:
            raise PromptIntelligenceError(
                409, 'DIRECTION_NOT_UNDER_BRIEF',
                f'direction {direction_id} belongs to brief {direction["brief_id"]}, not {brief["brief_id"]}')
        if direction['superseded_by']:
            raise PromptIntelligenceError(
                409, 'STALE_REVISION',
                f'direction {direction_id} version {direction["version"]} was superseded by '
                f'{direction["superseded_by"]}')
        return direction

    # -- reversal ---------------------------------------------------------------

    def reverse(self, project_id, asset_id, *, module, detections, decomposition_id=None):
        """Describe a stored asset as a prompt, from observations the caller supplies."""
        try:
            derived = self.analysis.derive(project_id, asset_id, module=module,
                                           detections=detections,
                                           decomposition_id=decomposition_id)
        except ImageAssetError as exc:
            # Same answer for "not yours" and "never imported", and a detail the caller can act on
            # rather than a tuple repr from another layer's exception.
            raise PromptIntelligenceError(
                exc.status, exc.code,
                f'asset {asset_id} is not a stored image of project {project_id}') from None
        except AssetAnalysisError as exc:
            raise PromptIntelligenceError(400, exc.code, exc.detail) from None

        rir = derived['rir']
        layers = []
        texts = []
        for node in rir['layers']:
            layers.append({'id': node['id'], 'type': node['type'], 'name': node['name'],
                           'bounds': node['bounds'], 'confidence': node['confidence']})
            if node['type'] == 'text':
                texts.append(node['text']['content'])

        canvas = rir['canvas']
        lines = [f'recreate a {canvas["width"]}x{canvas["height"]} {canvas["colorSpace"]} canvas',
                 f'{len(layers)} observed regions: '
                 + ', '.join(f'{layer["type"]} {layer["id"]}' for layer in layers)]
        if texts:
            lines.append('visible text, exactly as observed: ' + ' | '.join(texts))
        prompt_text = '\n'.join(lines)

        selection = self.selection.readback(project_id)
        chosen = selection['selection'] if selection['state'] == 'CHOSEN' else None
        return check_document({
            'schemaVersion': REVERSAL_VERSION,
            'reversal_id': 'reversal-' + _digest(
                [project_id, derived['asset']['id'], derived['asset']['sha256'],
                 derived['decomposition_id'], prompt_text]),
            'project_id': project_id,
            'asset': derived['asset'],
            'observation': {'module': module, 'decomposition_id': derived['decomposition_id'],
                            'rir_sha256': derived['rir_sha256'],
                            'object_count': derived['object_count']},
            'prompt_text': prompt_text,
            'layers': layers,
            'unknown': [
                {'field': 'semantic content',
                 'reason': 'no qualified vision backend exists, so no code path read the pixels; '
                           'every region here comes from the caller-supplied observations'},
                {'field': 'colour', 'reason': 'the analysis lowers no solid fill; style overrides were '
                                              'not supplied on this path'},
                {'field': 'font', 'reason': 'fontCandidates is empty in the IR; no face was matched'},
            ],
            'model': {'selected': chosen, 'selection_state': selection['state'],
                      'executed': False},
            'claims_not_made': [
                'this is not a description of what the image depicts: it restates recorded observations',
                'the confidence values belong to the supplied observation module, not to this product',
                'no model ran and no host was called',
            ],
        }, REVERSAL_SCHEMA_PATH, 'reversal')

    # -- readback ---------------------------------------------------------------

    @staticmethod
    def readback(document) -> dict:
        """Return the document with its own digest, so a caller can prove nothing was edited after."""
        body = json.dumps(document, sort_keys=True, ensure_ascii=False)
        return {'status': 'PROMPT_READBACK', 'document': document,
                'document_sha256': 'sha256:' + hashlib.sha256(body.encode('utf-8')).hexdigest()}

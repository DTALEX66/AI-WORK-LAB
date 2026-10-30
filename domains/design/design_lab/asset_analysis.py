# SPDX-License-Identifier: MIT
"""Turn a stored raster asset plus an explicit OCR observation into a reconstruction IR.

The bridge already existed and was tested: ``analysis.decomposition.Plan.from_ocr`` maps bounded convex
quadrilaterals and ``analysis.plan_to_rir`` lowers a Plan to a schema-valid
``design-lab/reconstruction-ir/v1``. What never existed was a caller outside ``design-lab/tests``, so the
only structure a target package could carry was what a person typed into the page. This module is that
missing seam: it reads bytes the asset store already verified and hands them to the existing bridge.

It performs no inference and calls no model. OCR observations are supplied by the caller, because no
local OCR backend is qualified today (``design-lab/readiness/model-radar.json`` reports
``QUALIFIED_LOCAL=0`` and every entry ``default_enabled: false``). An empty or absent observation list is
refused rather than answered with an empty document, because an empty IR would read like an analysis that
found nothing.

The produced document binds itself to the stored bytes through ``provenance.evidence``, which carries the
img-ID the import route registered rather than a filesystem path. A ``raster`` node appears only when
``materialize_raster_regions`` stages one, so an unmaterialised remainder stays a group marked
``inferred`` — the bridge never invents a background layer to fill the gap.
"""
from __future__ import annotations

import hashlib
import json

from .analysis.decomposition import DecompositionError, Plan
from .analysis.plan_to_rir import plan_to_rir
from .image_assets import ImageAssets
from .runtime.paths import PROJECT_ROOT


class AssetAnalysisError(Exception):
    """A refusal carrying a machine-readable code; it never leaves a partial document behind."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


class AssetAnalysis:
    def __init__(self, service):
        self.service = service
        self.assets = ImageAssets(service)

    def derive(self, project_id, asset_id, *, module, detections, decomposition_id=None,
               timestamp=None):
        """Return the IR document for one stored asset and one explicit observation set.

        `timestamp` is passed through to the bridge deliberately. Left unset, every node carries the
        wall clock of this call at one-second granularity, so the document digest is not stable and two
        calls that happen to land in the same second will look reproducible when they are not. A caller
        who needs a re-computable artefact pins one, the same convention `build_candidate` uses for
        `created_at`.
        """
        if not isinstance(module, str) or not 0 < len(module) <= 64:
            raise AssetAnalysisError('INVALID_MODULE',
                                     'module must be one short string naming the observation backend')
        if not isinstance(detections, list) or not detections:
            raise AssetAnalysisError(
                'NO_OBSERVATIONS',
                'an empty observation list lowers to no objects; refusing to emit an IR that looks '
                'like an analysis that found nothing')

        try:
            record = self.assets.content(project_id, asset_id)['asset']
        except DecompositionError as exc:                      # pragma: no cover - defensive
            raise AssetAnalysisError('INVALID_OBSERVATION', str(exc)) from exc

        identity = decomposition_id or ('decomp-' + hashlib.sha256(
            f'{record["sha256"]}|{module}|{len(detections)}'.encode('utf-8')).hexdigest()[:32])
        try:
            plan = Plan.from_ocr(decomposition_id=identity, source_ref=asset_id,
                                 source_sha256=record['sha256'],
                                 canvas=(record['width'], record['height']),
                                 module=module, detections=detections)
        except DecompositionError as exc:
            # The bridge refuses host claims (extra keys), unbounded lists and bad geometry. That
            # refusal is the product answer; restating it as a 200 with a shrunk document is not.
            raise AssetAnalysisError('INVALID_OBSERVATION', str(exc)) from exc

        rir = plan_to_rir(plan, raster_path=asset_id, project_root=PROJECT_ROOT,
                          timestamp=timestamp)
        return {
            'status': 'ASSET_ANALYSIS',
            'decomposition_id': identity,
            'asset': {'id': record['id'], 'sha256': record['sha256'],
                      'width': record['width'], 'height': record['height'],
                      'media_type': record['media_type']},
            'object_count': len(plan.objects),
            'rir': rir,
            'rir_sha256': 'sha256:' + hashlib.sha256(
                json.dumps(rir, sort_keys=True).encode('utf-8')).hexdigest(),
            'proves': ('E2 structural: bytes read back from the asset store and lowered by the existing '
                       'bridge. It proves no host run, no human acceptance, and no model quality.'),
        }

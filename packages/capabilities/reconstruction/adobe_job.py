# SPDX-License-Identifier: MIT
"""Closed, immutable Adobe host-job projection from validated reconstruction RIR."""
from __future__ import annotations

import hashlib
import json
import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import ContractError, validate_rir


ALLOWED_OPERATIONS = frozenset({
    "createDocument", "createLayer", "placePath", "placeText", "placeRaster", "applyMask",
    "saveAI", "reopen", "readback", "exportPNG", "exportSVG",
})
_DEFAULT_OPERATIONS = (
    "createDocument", "createLayer", "placePath", "placeText", "placeRaster", "applyMask",
    "saveAI", "exportSVG", "reopen", "readback", "exportPNG",
)


class AdobeJobError(ContractError):
    """A host-job is malformed, outside its run root, or requests a forbidden operation."""


def canonical_rir_hash(rir: dict[str, Any], *, project_root=None) -> str:
    validate_rir(rir, project_root=project_root)
    return hashlib.sha256(json.dumps(rir, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AdobeHostJob:
    job_id: str
    rir_hash: str
    run_root: Path
    artboard: dict[str, Any]
    layers: tuple[dict[str, Any], ...]
    assets: tuple[dict[str, Any], ...]
    targets: dict[str, Path]
    operations: tuple[str, ...]
    authorization: dict[str, Any]

    def target_paths(self) -> tuple[Path, ...]:
        return tuple(self.targets.values())

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy({
            "schemaVersion": "design-lab/adobe-host-job/v1",
            "jobId": self.job_id,
            "rirHash": self.rir_hash,
            "runRoot": str(self.run_root),
            "artboard": self.artboard,
            "layers": list(self.layers),
            "assets": list(self.assets),
            "targets": {key: str(value) for key, value in self.targets.items()},
            "operations": list(self.operations),
            "authorization": self.authorization,
        })


def _run_root(path: Path) -> Path:
    path = path.absolute()
    for part in (path, *path.parents):
        if part.exists() and (part.is_symlink() or getattr(part.lstat(), 'st_file_attributes', 0) & 1024):
            raise AdobeJobError('Adobe job root may not traverse links')
    try:
        root = path.resolve(strict=True)
    except OSError as exc:
        raise AdobeJobError("Adobe job run root must already exist") from exc
    if not root.is_dir() or root.is_symlink():
        raise AdobeJobError("Adobe job run root must be a regular directory")
    return root


def _inside(path: Path, root: Path) -> Path:
    if not path.is_absolute() or '..' in path.parts:
        raise AdobeJobError('absolute path without parent traversal required')
    try:
        path.relative_to(root)
    except ValueError:
        raise AdobeJobError('Adobe host target escapes the run root') from None
    for part in (path, *path.parents):
        if part.exists() and (part.is_symlink() or getattr(part.lstat(), 'st_file_attributes', 0) & 1024):
            raise AdobeJobError('Adobe job path may not traverse links')
    target = path.resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError:
        raise AdobeJobError("Adobe host target escapes the run root") from None
    return target


def _target_map(root: Path) -> dict[str, Path]:
    outputs = {
        "ai": root / "master.ai",
        "png": root / "illustrator-preview.png",
        "svg": root / "master.illustrator.svg",
    }
    return {key: _inside(path, root) for key, path in outputs.items()}


def validate_adobe_job(value: dict[str, Any]) -> None:
    required = {
        "schemaVersion", "jobId", "rirHash", "runRoot", "artboard", "layers", "assets",
        "targets", "operations", "authorization",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise AdobeJobError("Adobe job has an unexpected shape")
    if value["schemaVersion"] != "design-lab/adobe-host-job/v1":
        raise AdobeJobError("Adobe job schema version is unsupported")
    if not isinstance(value["jobId"], str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}',value['jobId']):
        raise AdobeJobError("Adobe job id is invalid")
    if not isinstance(value["rirHash"], str) or not re.fullmatch(r'[0-9a-f]{64}',value['rirHash']) or value['rirHash']=='0'*64:
        raise AdobeJobError("Adobe job RIR hash is invalid")
    root = _run_root(Path(value["runRoot"]))
    artboard = value["artboard"]
    if not isinstance(artboard, dict) or set(artboard)!={'width','height'} or not all(type(artboard.get(key)) is int and 1 <= artboard[key] <= 16383 for key in ("width", "height")):
        raise AdobeJobError("Adobe job artboard is invalid")
    if not isinstance(value["operations"], list) or tuple(value["operations"]) != _DEFAULT_OPERATIONS:
        raise AdobeJobError("Adobe job operations are not the exact allowlist sequence")
    targets = value["targets"]
    if not isinstance(targets, dict) or set(targets) != {'ai','png','svg'}:
        raise AdobeJobError("Adobe job targets are invalid")
    for kind,path in targets.items():
        if not isinstance(path, str):
            raise AdobeJobError("Adobe job target is not a string path")
        _inside(Path(path), root)
        if Path(path).suffix.lower()!='.'+kind or Path(path).exists():
            raise AdobeJobError('output extension invalid or output already exists')
    authorization = value["authorization"]
    if authorization != {"required": True, "scope": "single-session"} or authorization['required'] is not True:
        raise AdobeJobError("Adobe job authorization policy is invalid")
    from .adobe_lowering import validate_objects
    validate_objects(value,root)


def _project_owner(project_root, run_dir):
    if project_root is None:
        if __package__.startswith('design_lab.'):
            raise AdobeJobError('installed reconstruction requires an explicit project root')
        return Path(__file__).resolve().parents[3]
    from design_lab.runtime.paths import resolve_paths
    paths = resolve_paths(project_root=project_root)
    paths.checked_path(run_dir)
    return paths.project_root


def build_adobe_job(rir: dict[str, Any], run_dir: Path, *, text_styles=None, project_root=None) -> AdobeHostJob:
    """Project a validated RIR into one host-owned job without opening a creative application."""

    owner = _project_owner(project_root, run_dir)
    rir_hash = canonical_rir_hash(rir, project_root=owner)
    root = _run_root(Path(run_dir))
    targets = _target_map(root)
    from .adobe_lowering import lower_layers
    layers, assets = lower_layers(rir, root, text_styles or {}, project_root=owner)
    job = AdobeHostJob(
        f"adobe-{rir_hash[:24]}",
        rir_hash,
        root,
        {"width": rir["canvas"]["width"], "height": rir["canvas"]["height"]},
        tuple(layers),
        tuple(assets),
        targets,
        _DEFAULT_OPERATIONS,
        {"required": True, "scope": "single-session"},
    )
    validate_adobe_job(job.to_dict())
    return job


def build_photoshop_job(rir: dict[str, Any], run_dir: Path, *, text_styles=None, project_root=None) -> dict[str, Any]:
    """Lower the same validated RIR to editable text and independent PSD layers.

    General vector paths remain Illustrator-only until a qualified Photoshop
    path consumer exists. This function never silently rasterizes a reference.
    """
    from .adobe_lowering import lower_layers, validate_objects, require
    owner = _project_owner(project_root, run_dir)
    rir_hash = canonical_rir_hash(rir, project_root=owner)
    root = _run_root(Path(run_dir))
    width, height = rir['canvas']['width'], rir['canvas']['height']
    require(type(width) is int and type(height) is int and 1 <= width <= 16383
            and 1 <= height <= 16383 and width * height <= 25_000_000, 'unsupported Photoshop canvas')
    for name in ('master.psd', 'photoshop-preview.png'):
        require(not _inside(root / name, root).exists(), 'Photoshop output already exists')
    layers, assets = lower_layers(rir, root, text_styles or {}, project_root=owner)
    validate_objects(dict(layers=layers, assets=assets), root)

    def rectangle(item):
        points = item['points']
        require(item['closed'] and len(points) == 4, 'Photoshop requires an explicit rectangular fill/mask')
        anchors = [p['anchor'] for p in points]
        require(all(p['left'] == p['anchor'] == p['right'] for p in points), 'Photoshop curved paths unsupported')
        xs, ys = sorted(set(p[0] for p in anchors)), sorted(set(p[1] for p in anchors))
        require(len(xs) == len(ys) == 2 and len(set(map(tuple, anchors))) == 4, 'nonrectangular path unsupported')
        require(all((anchors[i][0] == anchors[(i+1)%4][0]) != (anchors[i][1] == anchors[(i+1)%4][1])
                    for i in range(4)), 'crossed rectangle unsupported')
        x, y, w, h = xs[0], height-ys[1], xs[1]-xs[0], ys[1]-ys[0]
        require(x >= 0 and y >= 0 and x+w <= width and y+h <= height, 'rectangle outside Photoshop canvas')
        return [x, y, w, h]

    def convert(item):
        kind = item['kind']
        if kind == 'path':
            return dict(id=item['id'], kind='fill', bounds=rectangle(item), color=item['color'])
        if kind == 'group':
            return dict(id=item['id'], kind='group', children=[convert(n) for n in item['items']],
                        mask=rectangle(item['mask']) if item['mask'] is not None else None)
        require(kind in ('text', 'raster'), 'Photoshop compound paths unsupported')
        result = copy.deepcopy(item)
        result['position'] = [item['position'][0], height-item['position'][1]]
        require(all(0 <= v <= 16383 for v in result['position']), 'Photoshop position out of range')
        return result

    return dict(schemaVersion='design-lab/photoshop-native-job/v1', jobId='ps-'+rir_hash[:24],
                runRoot=str(root), width=width, height=height, outputName='master.psd',
                previewName='photoshop-preview.png', assets=assets,
                layers=[convert(n) for layer in layers for n in layer['items']])

# SPDX-License-Identifier: MIT
"""Scoped cache inventory. Structural bytes never imply model inference."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from ..runtime.paths import resolve_paths
from .model_manifest import checked_cache_root, verify_model_files


def _repo_ids(values):
    ids = list(values)
    if any(not isinstance(value, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", value)
            or any(part in (".", "..") for part in value.split("/")) for value in ids):
        raise ValueError("invalid model repository ID")
    return ids


class ModelCacheProbe:
    """Read-only explicit caches, with optional reviewed per-model manifests.

    Ambient HF_HOME/MODELSCOPE_CACHE and user profile caches are not searched.
    Supplying a manifest cannot cause downloads or model execution.
    """
    def __init__(self, hf_home: Path | None = None, modelscope_home: Path | None = None,
                 *, manifests=None, project_root=None):
        self.project_root = project_root
        layout = resolve_paths(project_root=project_root)
        self.hf_home = checked_cache_root(hf_home if hf_home is not None else
                                         layout.model_cache / "huggingface", project_root=project_root)
        self.hf_hub = self.hf_home / "hub"
        self.modelscope_home = checked_cache_root(modelscope_home if modelscope_home is not None else
                                                  layout.model_cache / "modelscope", project_root=project_root)
        self.manifests = {} if manifests is None else manifests

    def hf_report(self, repo_dir: Path, manifest=None):
        repo_dir = Path(repo_dir)
        if not repo_dir.is_relative_to(self.hf_hub):
            raise ValueError("model directory is outside the selected HuggingFace cache")
        return verify_model_files(repo_dir, manifest, project_root=self.project_root)

    def hf_readiness(self, repo_dir: Path) -> str:
        return self.hf_report(repo_dir)["state"]

    def _report(self, repo_id, root):
        manifest = self.manifests.get(repo_id)
        if manifest is not None and (not isinstance(manifest, dict) or manifest.get("model_id") != repo_id):
            raise ValueError("model manifest identity mismatch")
        return verify_model_files(root, manifest, project_root=self.project_root)

    def probe_hf(self, repo_ids: Iterable[str]) -> dict[str, str]:
        return {repo_id: self._report(repo_id, self.hf_hub / ("models--" + repo_id.replace("/", "--")))["state"]
                for repo_id in _repo_ids(repo_ids)}

    def probe_modelscope(self, model_ids: Iterable[str]) -> dict[str, str]:
        return {model_id: self._report(model_id, self.modelscope_home / model_id.replace("/", "--"))["state"]
                for model_id in _repo_ids(model_ids)}


# Historical candidate IDs only; not verified presence, license or availability.
OCR_CANDIDATES = (
    "PaddlePaddle/PP-OCRv6_medium_det",
    "PaddlePaddle/PP-OCRv6_medium_rec",
    "PaddlePaddle/PP-LCNet_x1_0_doc_ori",
    "PaddlePaddle/PP-LCNet_x1_0_textline_ori",
    "PaddlePaddle/UVDoc",
)
ASR_CANDIDATES = (
    "Systran/faster-whisper-base",
    "Systran/faster-whisper-tiny",
)
MODELSCOPE_CANDIDATES = (
    "iic/SenseVoiceSmall",
)


@dataclass(frozen=True)
class BackendReadiness:
    capability: str
    ready: bool
    detail: dict[str, str]

    @property
    def status(self) -> str:
        return "INFERENCE_VERIFIED" if self.ready else "NOT_INFERENCE_VERIFIED"


def ocr_backend_ready(probe: ModelCacheProbe | None = None) -> BackendReadiness:
    """Both detection and recognition need real inference, not cached bytes."""
    states = (probe or ModelCacheProbe()).probe_hf(OCR_CANDIDATES)
    return BackendReadiness("ocr", all(states.get(model) == "INFERENCE_VERIFIED"
                                      for model in OCR_CANDIDATES[:2]), states)


def asr_backend_ready(probe: ModelCacheProbe | None = None) -> BackendReadiness:
    """ASR is transcription only, never speech generation."""
    states = (probe or ModelCacheProbe()).probe_hf(ASR_CANDIDATES)
    return BackendReadiness("asr", any(s == "INFERENCE_VERIFIED" for s in states.values()), states)

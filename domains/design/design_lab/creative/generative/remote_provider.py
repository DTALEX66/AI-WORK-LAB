# SPDX-License-Identifier: MIT
"""DL-P0-090 Remote generative provider: the record, not the call.

A hosted provider (Replicate-class HTTP API) is treated as an untrusted remote
execution: DESIGN-LAB records the exact request identity, the provider's
response, and the local readback of the downloaded bytes. Three rules hold:

* the repository never holds a credential — the caller supplies an authorized
  host-side transport, and this module refuses to look for one;
* a remote ``succeeded`` response is not evidence: only a local artifact digest
  plus a local readback digest qualifies an output;
* remote outputs carry a different rights position from local generation, so a
  receipt must carry the territory/commercial state instead of assuming it.
"""
from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from ...adapters.spi import ProviderAdapter
from ...runtime.attempt_contract import canonical_hash, request_hash
from ...runtime.paths import PROJECT_ROOT
from .errors import GenerativeError

RECEIPT_SCHEMA = PROJECT_ROOT / "design-lab/schemas/generative-remote-receipt.schema.json"
SCHEMA_VERSION = "design-lab/generative-remote-receipt/v1"
STATUSES = ("starting", "processing", "succeeded", "failed", "canceled")
INPUT_SOURCES = ("upload", "url", "asset_version")
CAPABILITY = "image.generate.remote"


def build_request(*, model_ref: str, version_ref: str, inputs, params=None, webhook=False) -> dict:
    """Canonical remote request. Inputs are digests and roles, never credentials."""
    if not isinstance(model_ref, str) or not model_ref.strip():
        raise GenerativeError("model_ref must be a nonempty string")
    if not isinstance(version_ref, str) or not version_ref.strip():
        raise GenerativeError("version_ref must be a nonempty string, not 'latest'")
    if version_ref.strip().lower() in {"latest", "current", "default"}:
        raise GenerativeError("a remote request must pin an exact model version, not a moving alias")
    entries = []
    for item in inputs or ():
        if not isinstance(item, dict):
            raise GenerativeError("every input must be an object")
        unknown = set(item) - {"role", "sha256", "source", "asset_version_id"}
        if unknown:
            raise GenerativeError("unknown input field: " + ", ".join(sorted(unknown)))
        source = item.get("source", "upload")
        if source not in INPUT_SOURCES:
            raise GenerativeError(f"unknown input source: {source!r}")
        digest = item.get("sha256")
        if digest is not None:
            digest = canonical_hash(digest)
        if source == "asset_version" and not item.get("asset_version_id"):
            raise GenerativeError("an asset_version input requires asset_version_id")
        entries.append({"role": item.get("role") or "input", "sha256": digest, "source": source,
                        "asset_version_id": item.get("asset_version_id")})
    if not entries:
        raise GenerativeError("a remote request requires at least one input")
    for key in ("key", "api_key", "token", "authorization", "secret"):
        if key in (params or {}):
            raise GenerativeError("credentials never enter a request record; the transport is host-side")
    request = {"model_ref": model_ref, "version_ref": version_ref, "inputs": entries,
               "params": dict(params or {}), "webhook": bool(webhook)}
    request["request_sha256"] = request_hash(request)
    return request


def parse_response(payload) -> dict:
    """Normalize a provider response; unknown statuses fail closed."""
    if not isinstance(payload, dict):
        raise GenerativeError("provider response must be an object")
    status = payload.get("status")
    if status not in STATUSES:
        raise GenerativeError(f"unknown provider status: {status!r}")
    outputs = []
    for item in payload.get("output") or ():
        if isinstance(item, str):
            outputs.append({"kind": "url", "ref_sha256": request_hash({"url": item})})
        elif isinstance(item, dict):
            digest = item.get("sha256")
            outputs.append({"kind": item.get("kind", "url"),
                            "ref_sha256": canonical_hash(digest) if digest else request_hash(item)})
        else:
            raise GenerativeError("provider outputs must be strings or objects")
    metrics = payload.get("metrics") or {}
    if not isinstance(metrics, dict):
        raise GenerativeError("provider metrics must be an object")
    return {"prediction_id": payload.get("id"), "status": status, "outputs": outputs,
            "metrics": metrics, "error": payload.get("error"),
            "model_version": (payload.get("version") if isinstance(payload.get("version"), str) else None)}


def to_receipt(request: dict, response: dict, *, local_artifact_sha256=None, readback_sha256=None,
               rights_state: str = "UNKNOWN", territory_limits=()) -> dict:
    """Combine request, response and LOCAL readback into one receipt record."""
    for field in ("request_sha256", "model_ref", "version_ref"):
        if field not in request:
            raise GenerativeError(f"not a recorded request: missing {field}")
    if response.get("status") not in STATUSES:
        raise GenerativeError("receipt requires a normalized response")
    local = canonical_hash(local_artifact_sha256) if local_artifact_sha256 else None
    readback = canonical_hash(readback_sha256) if readback_sha256 else None
    qualified = response["status"] == "succeeded" and local is not None and readback is not None
    receipt = {
        "schemaVersion": SCHEMA_VERSION,
        "provider_kind": "REMOTE_HOSTED",
        "model_ref": request["model_ref"],
        "version_ref": request["version_ref"],
        "request_sha256": request["request_sha256"],
        "params_sha256": request_hash(request.get("params") or {}),
        "input_sha256": sorted(item["sha256"] for item in request["inputs"] if item["sha256"]),
        "prediction_id": response.get("prediction_id"),
        "provider_status": response["status"],
        "output_refs": response.get("outputs", []),
        "metrics": response.get("metrics", {}),
        "local_artifact_sha256": local,
        "readback_sha256": readback,
        "rights": {"state": rights_state, "territory_limits": sorted(territory_limits)},
        "axes": {"implementation": "IMPLEMENTED_LOCAL",
                 "unit": "PASS" if qualified else "PARTIAL",
                 "host_live": "PASS" if qualified else "NOT_VERIFIED",
                 "delivery": "PARTIAL"},
        "limitations": [
            "remote success is not acceptance: a local artifact digest and a local readback are required",
            "remote output rights differ from locally generated output; the rights state must be adjudicated",
            "no credential is stored or discovered by this module",
        ],
    }
    schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(receipt))
    if errors:
        raise GenerativeError(f"remote receipt violates its schema: {errors[0].message}")
    return receipt


def assert_local_evidence(receipt: dict) -> None:
    """A receipt may not claim success without local artifact and readback bytes."""
    if receipt.get("provider_status") != "succeeded":
        return
    for field in ("local_artifact_sha256", "readback_sha256"):
        value = receipt.get(field)
        if not value:
            raise GenerativeError(f"remote success lacks {field}; the output is unverified")
        canonical_hash(value)


def unsupported_claims(receipt: dict) -> list:
    claims = []
    if not receipt.get("local_artifact_sha256"):
        claims.append("artifact_available")
    if not receipt.get("readback_sha256"):
        claims.append("output_readable")
    if receipt.get("rights", {}).get("state") != "CLEARED":
        claims.append("commercial_use")
    claims.append("reproducible_offline")
    return sorted(claims)


def credentials_boundary() -> dict:
    """The repository holds no remote credentials and does not look for any."""
    return {"in_repo_credentials": "FORBIDDEN", "credential_source": "host-side caller only",
            "env_lookup": "NOT_PERFORMED", "logged": False}


class ReplicateProvider(ProviderAdapter):
    """Structural remote provider. Never performs an HTTP call in this build."""

    adapter_id = "provider:remote/replicate"
    adapter_type = "provider"
    version = "design-lab/remote-provider/v1"

    def probe(self, ctx: dict) -> dict:
        return {"adapter_id": self.adapter_id, "status": "STRUCTURAL", "evidence_level": "E1",
                "live_probe": "NOT_EXECUTED",
                "capabilities": [{"name": CAPABILITY, "supported": False,
                                  "note": "record structure and receipts only; no hosted call is made"}],
                "credentials": credentials_boundary()}

    def prepare(self, ctx: dict) -> dict:
        request = build_request(**{key: ctx[key] for key in
                                   ("model_ref", "version_ref", "inputs") if key in ctx},
                                params=ctx.get("params"))
        return {"adapter_id": self.adapter_id, "request": request, "prepared": True, "dispatched": False}

    def execute(self, envelope: dict) -> dict:
        raise GenerativeError(
            "NOT_EXECUTED_STRUCTURAL_ONLY: a hosted call requires a credentialed host-side transport, "
            "owner-approved usage terms and an outbound network policy; this build makes no remote call")

    def observe(self, ctx: dict) -> dict:
        return {"adapter_id": self.adapter_id, "observed": False, "reason": "NOT_EXECUTED",
                "expected_observations": ["prediction status transitions", "provider metrics"]}

    def readback(self, ctx: dict) -> dict:
        return {"adapter_id": self.adapter_id, "readback": "NOT_EXECUTED",
                "expected_readback": ["downloaded artifact digest", "local decoder readback digest"]}

    def rollback(self, ctx: dict) -> dict:
        return {"adapter_id": self.adapter_id, "rollback": "PLAN_ONLY",
                "steps": ["discard the staged remote output", "cancel the prediction when still running",
                          "release the asset writer lease"]}

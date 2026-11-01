# -*- coding: utf-8 -*-
"""AG-05: fail-closed integrity verifier for the model/provider/runtime registries.

Authority chain: `WORK-LAB-AUTHORITY.md` > `.project/governance/project-authority-index.json`
> `AGENTS.md` + scoped machine contracts > this verifier. This script never
mutates anything and never touches the network, a model asset, a runtime
process, or any global software configuration. It reads JSON only.

Why this exists
---------------
The 2026-09-29 Master Atlas recorded that the three registries disagreed with
each other (gap G05, card row AG-05): a provider bound to a model id that no
longer existed, provider entries that claimed `OPERATIONAL` while their own
notes said the weight was not served, digests that were truncated prose rather
than verifiable checksums, and in-process ASR libraries that were not
distinguishable from HTTP servers. Each is a silent-wrong-truth hazard: a
caller reading one field concludes a capability is callable when it is not.

Checks (every one fails closed with a named reason)
--------------------------------------------------
1  `binds_to_model` must resolve to a `models[].id`, or to an explicitly
   declared `externalAssets[].id` (a read-only reference the registry does not
   own), or be an explicit `null` with a non-empty `binding_note` explaining
   why there is no binding. A dangling foreign key is a failure.
2  `binds_to_runtime` must resolve to a `runtimes[].id` or a
   `processLibraries[].id`. In-process libraries are declared distinctly from
   HTTP servers via `executionModel`, so a process library is never mistaken
   for a service that can be polled.
3  `binding_status` is a closed vocabulary. A provider whose model entry is
   RETIRED_PENDING_DECISION must declare `UNSERVED_RETAINED_PENDING_DECISION`
   and must NOT declare `SERVED`. This is the contradiction check: an entry may
   not simultaneously be "not served" and "served".
4  `operationalStatus` is explicitly scoped to the runtime endpoint and may not
   use serving vocabulary ("loads this model", "serves this model") when the
   binding is not served. That phrasing is what made the old rows read as
   "this model works".
5  An `assetDigest` block is either absent, or has `state: COMPLETE` with a
   lowercase 64-hex `sha256`, or has `state: TRUNCATED` with a non-empty
   reason. A truncated prefix may never masquerade as a complete digest.
6  A provider id appears at most once; provider ids are namespaced.
7  AG-05g: a model that carries a `sha256`, or a `health` word containing VERIFIED,
   or a retired-with-decision status, must carry a `localVerification` block naming
   presence, digest state, bytes seen, the date, the basis and the tool; a
   RECOMPUTED_MATCH must agree with `sha256` and with `file.bytes`, a VERIFIED health
   word may not sit on an unrecomputed digest, and a leftover-file (`candidateOrphans`)
   record must say whether the file is still there — including the honest answer that
   its path was written as prose and cannot be resolved at all.

Exit codes: 0 PASS, 1 FAIL (named reason printed), 2 environment error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROVIDER_REGISTRY = ".project/governance/provider-registry.json"
MODEL_REGISTRY = ".project/governance/model-registry.json"
RUNTIME_REGISTRY = ".project/governance/runtime-registry.json"

# Closed vocabulary for the provider -> model binding state (AG-05).
BINDING_STATUSES = frozenset({"SERVED", "UNSERVED_RETAINED_PENDING_DECISION"})
# Model-registry lifecycle values that mean "this weight is not served".
UNSERVED_MODEL_STATUSES = frozenset({"RETIRED_PENDING_DECISION", "RETIRED"})
# Digest states for the assetDigest block.
DIGEST_STATES = frozenset({"COMPLETE", "TRUNCATED"})
# AG-05g: how a byte claim was checked on the machine that owns the weights.
PRESENCE_STATES = frozenset({"VERIFIED_FILE", "VERIFIED_BLOB_CONTENT_ADDRESS",
                             "VERIFIED_DIR", "ABSENT", "UNRESOLVED", "NOT_CHECKED"})
DIGEST_VERIFICATION_STATES = frozenset({"RECOMPUTED_MATCH", "RECOMPUTED_MISMATCH",
                                        "NOT_RECOMPUTED"})
ORPHAN_RECHECK_STATES = frozenset({"PRESENT", "ABSENT_NOW", "UNRESOLVABLE_AS_WRITTEN"})
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

# AG-05f: closed vocabulary for structured negative capabilities. The Atlas G05
# acceptance wording explicitly requires "negative capabilities"; before this the
# registry expressed its limitations only in prose a machine consumer cannot read,
# so a caller could treat a partial capability as a full one.
NEGATIVE_STATES = frozenset({"UNAVAILABLE", "UNVERIFIED", "REFUSED"})

HEX64 = re.compile(r"^[0-9a-f]{64}$")
# Serving vocabulary that must not appear in a runtime-scoped operationalStatus
# when the provider's own binding is declared unserved.
SERVING_PHRASES = ("loads this model", "loads the model", "serves this model",
                   "this model is served", "model on demand")
# Fields that must never be null/empty when present.
_REQUIRED_PROVIDER_STRINGS = ("id",)

_errors: list[str] = []


def _fail(reason: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    _errors.append(f"{reason}{suffix}")


def _check_asset_digest(owner: str, digest: object) -> None:
    """Shared digest-honesty rule for any entry that carries assetDigest.

    A digest block is either absent, or COMPLETE with a lowercase 64-hex
    sha256, or TRUNCATED with a stated reason. A truncated prefix may never
    masquerade as a complete digest, and a bare prefix with no explanation is
    indistinguishable from a fabricated checksum.
    """
    if digest is None:
        return
    if not isinstance(digest, dict):
        _fail("ASSET_DIGEST_MALFORMED", f"{owner}.assetDigest must be an object")
        return
    state = digest.get("state")
    if state not in DIGEST_STATES:
        _fail("ASSET_DIGEST_STATE_UNKNOWN",
              f"{owner}.assetDigest.state={state!r} not in {sorted(DIGEST_STATES)}")
        return
    if state == "COMPLETE":
        sha = digest.get("sha256")
        if not (isinstance(sha, str) and HEX64.match(sha)):
            _fail("ASSET_DIGEST_INCOMPLETE",
                  f"{owner}.assetDigest.state=COMPLETE but sha256 is not 64 lowercase hex")
    elif state == "TRUNCATED":
        reason = digest.get("reason")
        if not (isinstance(reason, str) and reason.strip()):
            _fail("ASSET_DIGEST_TRUNCATED_WITHOUT_REASON",
                  f"{owner}.assetDigest.state=TRUNCATED requires a reason")


def _check_local_verification(owner: str, entry: dict) -> None:
    """A byte claim must say how it was checked, and agree with itself.

    `sha256` and a health word containing VERIFIED both read as "someone verified
    these bytes". Before AG-05g nothing recorded what the digest was taken over, when,
    or with what tool, so a copied-back upstream hash and a locally recomputed digest
    were indistinguishable in the machine authority. This is structural on purpose:
    the runner cannot see the weight root, so it checks the claim's internal
    consistency and `scripts/audit/model_library_readback.py` produces the numbers.
    """
    sha = entry.get("sha256")
    health = str(entry.get("health") or "").upper()
    claims_verified = "VERIFIED" in health
    verification = entry.get("localVerification")

    # A model that is being retired by an open decision must say what it still costs,
    # whether or not anyone ever hashed it. 0 is a legitimate answer; silence is not.
    if entry.get("status") in UNSERVED_MODEL_STATUSES:
        if not isinstance(verification, dict) or not isinstance(verification.get("bytesRetained"), int) \
                or verification.get("bytesRetained") < 0:
            _fail("RETIRING_MODEL_WITHOUT_A_COST",
                  f"{owner}: status={entry.get('status')!r} must record localVerification."
                  "bytesRetained as a byte count (0 once released), so a pending decision "
                  "carries the disk it actually occupies")
        else:
            retained = verification["bytesRetained"]
            presence = verification.get("presence")
            verified_present = presence in ("VERIFIED_FILE", "VERIFIED_BLOB_CONTENT_ADDRESS",
                                            "VERIFIED_DIR")
            if retained == 0 and verified_present:
                _fail("ZERO_RETAINED_WITH_VERIFIED_PRESENCE",
                      f"{owner}: bytesRetained=0 while presence={presence!r} claims the bytes are here")
            if retained > 0 and not verified_present:
                _fail("RETAINED_BYTES_WITHOUT_PRESENCE",
                      f"{owner}: bytesRetained={retained} but presence={presence!r} does not "
                      "claim the bytes are here")

    if sha is None and not claims_verified and verification is None:
        return
    if not isinstance(verification, dict):
        _fail("LOCAL_VERIFICATION_MISSING",
              f"{owner}: sha256 or a VERIFIED health word is a byte claim; it needs "
              "localVerification with presence, digestState, bytesObserved, checkedAt, "
              "basis and tool")
        return
    presence = verification.get("presence")
    if presence not in PRESENCE_STATES:
        _fail("LOCAL_VERIFICATION_PRESENCE_UNKNOWN",
              f"{owner}.localVerification.presence={presence!r} not in {sorted(PRESENCE_STATES)}")
    state = verification.get("digestState")
    if state not in DIGEST_VERIFICATION_STATES:
        _fail("LOCAL_VERIFICATION_STATE_UNKNOWN",
              f"{owner}.localVerification.digestState={state!r} not in "
              f"{sorted(DIGEST_VERIFICATION_STATES)}")
    if not DATE_RE.match(str(verification.get("checkedAt") or "")):
        _fail("LOCAL_VERIFICATION_UNDATED",
              f"{owner}.localVerification.checkedAt={str(verification.get('checkedAt'))[:24]!r} "
              "is not a date; an undated readback is not evidence")
    for field in ("basis", "tool"):
        if not str(verification.get(field) or "").strip():
            _fail("LOCAL_VERIFICATION_FIELD_MISSING",
                  f"{owner}.localVerification.{field} must say how the claim was checked")

    if state == "RECOMPUTED_MATCH":
        recomputed = verification.get("sha256Recomputed")
        if not (isinstance(recomputed, str) and HEX64.match(recomputed)):
            _fail("LOCAL_VERIFICATION_DIGEST_NOT_HEX",
                  f"{owner}.localVerification.sha256Recomputed must be 64 lowercase hex")
        elif sha != recomputed:
            _fail("LOCAL_VERIFICATION_CONTRADICTS_SHA256",
                  f"{owner}: digestState=RECOMPUTED_MATCH but sha256 and sha256Recomputed differ")
        observed = verification.get("bytesObserved")
        if not isinstance(observed, int) or observed <= 0:
            _fail("LOCAL_VERIFICATION_BYTES_MISSING",
                  f"{owner}: RECOMPUTED_MATCH requires a positive bytesObserved")
        stated_bytes = (entry.get("file") or {}).get("bytes")
        if isinstance(stated_bytes, int) and isinstance(observed, int) and stated_bytes != observed:
            _fail("LOCAL_VERIFICATION_BYTES_DISAGREE",
                  f"{owner}: file.bytes={stated_bytes} but bytesObserved={observed}")
        if presence in ("ABSENT", "UNRESOLVED", "NOT_CHECKED"):
            _fail("VERIFIED_MATCH_WITHOUT_PRESENCE",
                  f"{owner}: digestState=RECOMPUTED_MATCH with presence={presence!r}")
    if claims_verified and state != "RECOMPUTED_MATCH":
        _fail("HEALTH_CLAIMS_VERIFIED_WITHOUT_RECOMPUTATION",
              f"{owner}: health={str(entry.get('health'))[:60]!r} says VERIFIED while "
              f"digestState={state!r}; say what was verified, or stop claiming it")
    if presence == "VERIFIED_DIR" and not (verification.get("directoryManifest") or []):
        _fail("DIR_MANIFEST_MISSING",
              f"{owner}: a directory-backed model needs a per-file manifest, not one "
              "truncated prefix for one arbitrary file")


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _fail("REGISTRY_MISSING", str(path))
    except json.JSONDecodeError as exc:
        _fail("REGISTRY_INVALID_JSON", f"{path}: {exc}")
    return {}


def _index(entries: object, key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not isinstance(entries, list):
        return out
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get(key), str):
            out[entry[key]] = entry
    return out


def verify(root: Path) -> int:
    _errors.clear()
    provider_path = root / PROVIDER_REGISTRY
    if not provider_path.is_file():
        return _report("PROVIDER_REGISTRY_MISSING", str(provider_path))

    providers_doc = _load(provider_path)
    models_doc = _load(root / MODEL_REGISTRY)
    runtimes_doc = _load(root / RUNTIME_REGISTRY)
    if _errors:
        return _report("REGISTRY_UNREADABLE", "; ".join(_errors))

    providers = providers_doc.get("providers")
    if not isinstance(providers, list) or not providers:
        return _report("PROVIDERS_MISSING", "provider-registry.json has no providers[]")

    models = _index(models_doc.get("models"), "id")
    runtimes = _index(runtimes_doc.get("runtimes"), "id")
    process_libs = _index(runtimes_doc.get("processLibraries"), "id")
    # Every id a binding may legitimately resolve to (HTTP runtime or declared
    # in-process library). Computed up front because both the provider checks and
    # the model checks need it.
    known_runtimes = set(runtimes) | set(process_libs)
    external_assets = _index(providers_doc.get("externalAssets"), "id")

    known_bindings = set(models) | set(external_assets)

    seen_ids: set[str] = set()
    served_bindings = 0

    for provider in providers:
        if not isinstance(provider, dict):
            _fail("PROVIDER_ENTRY_MALFORMED", repr(provider)[:80])
            continue
        pid = provider.get("id")
        if not isinstance(pid, str) or not pid:
            _fail("PROVIDER_ID_MISSING", "every provider needs a non-empty id")
            continue
        if pid in seen_ids:
            _fail("PROVIDER_ID_DUPLICATE", pid)
        seen_ids.add(pid)
        for field in _REQUIRED_PROVIDER_STRINGS:
            if not isinstance(provider.get(field), str):
                _fail("PROVIDER_FIELD_MISSING", f"{pid}.{field}")

        # --- check 1: model foreign key -------------------------------
        bound = provider.get("binds_to_model")
        if bound is None:
            note = provider.get("binding_note")
            if not (isinstance(note, str) and note.strip()):
                _fail("BINDING_NULL_WITHOUT_NOTE",
                      f"{pid} declares binds_to_model=null without a binding_note")
        elif not isinstance(bound, str):
            _fail("BINDING_NOT_STRING", f"{pid}.binds_to_model={bound!r}")
        elif bound not in known_bindings:
            _fail("BINDING_UNRESOLVED",
                  f"{pid}.binds_to_model={bound!r} is not a models[].id "
                  f"({len(models)} known) nor a declared externalAssets[].id")

        # --- check 2: runtime foreign key -----------------------------
        runtime = provider.get("binds_to_runtime")
        if runtime is not None:
            if not isinstance(runtime, str):
                _fail("RUNTIME_BINDING_NOT_STRING", f"{pid}.binds_to_runtime={runtime!r}")
            elif runtime not in runtimes and runtime not in process_libs:
                _fail("RUNTIME_BINDING_UNRESOLVED",
                      f"{pid}.binds_to_runtime={runtime!r} is neither a runtimes[].id "
                      "nor a declared processLibraries[].id")

        model_entry = models.get(bound) if isinstance(bound, str) else None
        model_status = model_entry.get("status") if isinstance(model_entry, dict) else None
        binding_status = provider.get("binding_status")

        # --- check 3: binding-status closed vocabulary + contradiction --
        if binding_status is not None:
            if binding_status not in BINDING_STATUSES:
                _fail("BINDING_STATUS_UNKNOWN",
                      f"{pid}.binding_status={binding_status!r} not in {sorted(BINDING_STATUSES)}")
            if binding_status == "SERVED":
                served_bindings += 1
                if model_status in UNSERVED_MODEL_STATUSES:
                    _fail("BINDING_STATUS_CONTRADICTS_MODEL",
                          f"{pid} declares SERVED but model {bound!r} status={model_status!r}")
            source = provider.get("binding_status_source")
            if binding_status == "UNSERVED_RETAINED_PENDING_DECISION" \
                    and not (isinstance(source, str) and source.strip()):
                _fail("BINDING_STATUS_WITHOUT_SOURCE",
                      f"{pid} declares an unserved binding without binding_status_source")
        elif model_status in UNSERVED_MODEL_STATUSES:
            _fail("UNSERVED_MODEL_WITHOUT_BINDING_STATUS",
                  f"{pid} binds model {bound!r} (status={model_status!r}) but declares no "
                  "binding_status; the reader cannot tell the binding is dead")

        # --- check 4: operationalStatus is runtime-scoped only --------
        op_status = provider.get("operationalStatus")
        if isinstance(op_status, str) and binding_status == "UNSERVED_RETAINED_PENDING_DECISION":
            lowered = op_status.lower()
            for phrase in SERVING_PHRASES:
                if phrase in lowered:
                    _fail("OPERATIONAL_STATUS_OVERREACHES",
                          f"{pid} declares an unserved binding but its operationalStatus says "
                          f"{phrase!r}; that reads as 'this model works'")
        if isinstance(op_status, str) and "operational" in op_status.lower() \
                and binding_status is None and model_status in UNSERVED_MODEL_STATUSES:
            _fail("OPERATIONAL_STATUS_UNSCOPED",
                  f"{pid} claims OPERATIONAL with an unserved model and no bound scope")

        # --- check 5: digest honesty ----------------------------------
        _check_asset_digest(pid, provider.get("assetDigest"))

        # --- check: structured negative capabilities ----------------------
        # A limitation that exists only in prose is one an agent can miss and
        # then report a partial capability as complete. Every declared negative
        # capability must be typed, evidenced, and MUST NOT contradict a positive
        # capability the same provider declares.
        declared_caps = {str(c) for c in (provider.get("capabilities") or [])}
        negatives = provider.get("negative_capabilities")
        if negatives is None and "partial" in str(provider.get("provisional_reason") or "").lower():
            _fail("NEGATIVE_CAPABILITIES_MISSING",
                  f"{pid} declares a provisional/partial status without structured "
                  "negative_capabilities")
        for index, neg in enumerate(negatives or []):
            label = f"{pid}.negative_capabilities[{index}]"
            if not isinstance(neg, dict):
                _fail("NEGATIVE_CAPABILITY_MALFORMED", f"{label} must be an object")
                continue
            cap = neg.get("capability")
            if not isinstance(cap, str) or not cap:
                _fail("NEGATIVE_CAPABILITY_NO_NAME", f"{label} has no capability name")
                continue
            state = neg.get("state")
            if state not in NEGATIVE_STATES:
                _fail("NEGATIVE_CAPABILITY_STATE_UNKNOWN",
                      f"{label}.state={state!r} not in {sorted(NEGATIVE_STATES)}")
            if not (isinstance(neg.get("why"), str) and neg["why"].strip()):
                _fail("NEGATIVE_CAPABILITY_WITHOUT_WHY",
                      f"{label} states a limitation with no 'why'")
            if not (isinstance(neg.get("evidence"), str) and neg["evidence"].strip()):
                _fail("NEGATIVE_CAPABILITY_WITHOUT_EVIDENCE",
                      f"{label} states a limitation with no evidence pointer")
            # A negative entry whose name is exactly a positive capability means
            # the same provider both claims and denies it: refuse the ambiguity.
            if cap in declared_caps:
                _fail("NEGATIVE_CAPABILITY_CONTRADICTS_POSITIVE",
                      f"{label} denies {cap!r} while the provider also declares it in capabilities[]")

        # --- check: a runtime note may not name a DIFFERENT live runtime --
        # AG-05e. The provider's `runtime_note` described a different runtime
        # than `binds_to_runtime` (it said llama.cpp while the binding was
        # lmstudio), so a reader following the prose was pointed at the wrong
        # server. Historical narration is legitimate, but it must be marked as
        # such, not left reading as the current binding.
        bound_runtime = provider.get("binds_to_runtime")
        if isinstance(bound_runtime, str) and isinstance(rt_note := provider.get("runtime_note"), str):
            for other in sorted(known_runtimes):
                if other == bound_runtime:
                    continue
                if other.lower() not in rt_note.lower():
                    continue
                lowered = rt_note.lower()
                marked_historical = any(
                    marker in lowered for marker in
                    ("historical", "previously said", "superseded", "no longer",
                     "was measured on", "retained only", "corrected 2026")
                )
                if not marked_historical:
                    _fail("RUNTIME_NOTE_NAMES_OTHER_RUNTIME",
                          f"{pid}.runtime_note mentions {other!r} while binds_to_runtime is "
                          f"{bound_runtime!r}, without marking it historical")

    # --- check: model registry digest honesty -------------------------
    for model_id, entry in sorted(models.items()):
        raw = entry.get("sha256")
        if raw is not None and not (isinstance(raw, str) and HEX64.match(raw)):
            _fail("MODEL_SHA256_UNVERIFIABLE",
                  f"model {model_id}.sha256={str(raw)[:48]!r} is neither a 64-hex digest nor an "
                  "explicit null; move the prose to assetDigest and null the field")
        _check_asset_digest(f"model {model_id}", entry.get("assetDigest"))

    # --- check: a byte claim names how it was checked (AG-05g) --------
    # The registry's `health` strings had phrases like DOWNLOADED_HASH_VERIFIED and
    # a 64-hex `sha256` per model, while nothing on either side said what that digest
    # was a digest OF or when anyone last recomputed it. Shape checks could not see
    # the difference between a verified weight and a copied-back hash. So a claim
    # now needs a `localVerification` block: presence state, digest state, the bytes
    # seen, the recomputed digest, the date and the tool that produced it. This stays
    # a structural check on purpose — the CI runner has no weight root, and a required
    # job that can only skip there is worse than no job.
    for model_id, entry in sorted(models.items()):
        _check_local_verification(f"model {model_id}", entry)

    # --- check: residue/orphan entries obey the same digest honesty ----
    # candidateOrphans records leftover files (partial downloads, abandoned
    # pulls). They are not model assets, but a bare 16-hex prefix sitting in a
    # `sha256` field reads exactly like a checksum a tool might verify, so the
    # same COMPLETE-or-TRUNCATED-with-reason rule applies.
    for index, orphan in enumerate(models_doc.get("candidateOrphans") or []):
        if not isinstance(orphan, dict):
            continue
        label = f"candidateOrphans[{index}] ({str(orphan.get('path'))[:48]})"
        raw = orphan.get("sha256")
        if raw is not None and not (isinstance(raw, str) and HEX64.match(raw)):
            _fail("ORPHAN_SHA256_UNVERIFIABLE",
                  f"{label}.sha256={str(raw)[:32]!r} is neither 64-hex nor an explicit null")
        _check_asset_digest(label, orphan.get("assetDigest"))

        # AG-05g: a leftover-file record is a claim about the disk, so it must say
        # whether the file is still there. One of the two records described its path as
        # prose with an ellipsis, which no tool can resolve while the row keeps
        # asserting 3.4 GB of retained fragments.
        path_claim = str(orphan.get("path") or "")
        unresolvable = any(marker in path_claim for marker in ("…", "(", "+"))
        recheck = orphan.get("recheck")
        if not isinstance(recheck, dict):
            _fail("ORPHAN_RECHECK_MISSING",
                  f"{label}: a leftover-file claim must carry recheck with a state and a date, "
                  "otherwise a row about deleted data is indistinguishable from a row about kept data")
            continue
        rstate = recheck.get("state")
        if rstate not in ORPHAN_RECHECK_STATES:
            _fail("ORPHAN_RECHECK_STATE_UNKNOWN",
                  f"{label}.recheck.state={rstate!r} not in {sorted(ORPHAN_RECHECK_STATES)}")
        if not DATE_RE.match(str(recheck.get("checkedAt") or "")):
            _fail("ORPHAN_RECHECK_UNDATED", f"{label}.recheck.checkedAt is not a date")
        if unresolvable and rstate != "UNRESOLVABLE_AS_WRITTEN":
            _fail("ORPHAN_PATH_NOT_RESOLVABLE_AS_WRITTEN",
                  f"{label}: path {path_claim[:60]!r} contains prose, so it cannot be reported as "
                  "PRESENT or ABSENT; mark the recheck UNRESOLVABLE_AS_WRITTEN")
        if rstate == "PRESENT":
            observed = recheck.get("bytesObserved")
            if not isinstance(observed, int) or observed <= 0:
                _fail("ORPHAN_PRESENT_WITHOUT_BYTES", f"{label}: recheck=PRESENT needs bytesObserved")
            claimed = orphan.get("bytes")
            if isinstance(claimed, int) and isinstance(observed, int) and claimed != observed:
                _fail("ORPHAN_BYTES_DISAGREE",
                      f"{label}: claimed bytes={claimed} but observed {observed}")
            digest = recheck.get("sha256Recomputed")
            if not (isinstance(digest, str) and HEX64.match(digest)):
                _fail("ORPHAN_DIGEST_NOT_RECOMPUTED",
                      f"{label}: PRESENT requires the recomputed full sha256, not a prefix alone")
            prefix_claim = str((orphan.get("assetDigest") or {}).get("prefix") or "")
            if prefix_claim and isinstance(digest, str) and not digest.startswith(prefix_claim):
                _fail("ORPHAN_PREFIX_CLAIM_STALE",
                      f"{label}: the recorded {prefix_claim!r} prefix is not the head of the "
                      "recomputed digest, so the file is not the one that was registered")
            duplicate_of = recheck.get("byteDuplicateOf")
            if duplicate_of is None and recheck.get("duplicateTested") is not True:
                _fail("ORPHAN_DUPLICATE_UNTESTED",
                      f"{label}: a leftover may only be proposed for deletion against a proven "
                      "duplicate; record duplicateTested with the answer")

    # --- check: the model -> runtime binding is a RESOLVABLE id --------
    # The `runtime` field in model-registry.json is human-readable prose
    # ("lmstudio (:1234), BINARY VERDICT ONLY"), so it can never be used as a
    # foreign key — that is the same defect class as the OCR binding AG-05
    # fixed, where a descriptive string sat where an id belonged. A machine
    # consumer must use `runtime_id`, which is therefore required to resolve.
    known_runtimes = set(runtimes) | set(process_libs)
    for model_id, entry in sorted(models.items()):
        if "runtime_id" not in entry:
            _fail("MODEL_RUNTIME_ID_MISSING",
                  f"model {model_id} has no runtime_id; the sibling `runtime` field is prose and "
                  "must not be read as an id")
            continue
        runtime_id = entry.get("runtime_id")
        if runtime_id is None:
            # Explicitly unbound (retired/standby). Allowed, but the model must
            # not simultaneously claim to be served.
            status = entry.get("status")
            if status == "active":
                _fail("UNBOUND_RUNTIME_ON_ACTIVE_MODEL",
                      f"model {model_id} is status=active but runtime_id=null (nothing serves it)")
            continue
        if not isinstance(runtime_id, str) or runtime_id not in known_runtimes:
            _fail("MODEL_RUNTIME_ID_UNRESOLVED",
                  f"model {model_id}.runtime_id={runtime_id!r} is neither a runtimes[].id nor a "
                  f"processLibraries[].id ({sorted(known_runtimes)})")

    # --- check: process libraries are not HTTP servers ---------------
    for lib_id, lib in sorted(process_libs.items()):
        model = lib.get("executionModel")
        if model not in ("in-process", "subprocess"):
            _fail("PROCESS_LIBRARY_EXECUTION_MODEL",
                  f"processLibraries[{lib_id}].executionModel={model!r} must be "
                  "'in-process' or 'subprocess'")
        if lib.get("listensOnPort") not in (None, False):
            _fail("PROCESS_LIBRARY_CLAIMS_PORT",
                  f"processLibraries[{lib_id}] declares listensOnPort; an in-process library "
                  "must not be described as a service endpoint")

    # --- check: nothing claims to serve that is not served -----------
    for runtime_id, rt in sorted(runtimes.items()):
        status = rt.get("status")
        if isinstance(status, str) and status.strip().upper() == "RUNNING":
            for provider in providers:
                if not isinstance(provider, dict):
                    continue
                if provider.get("binds_to_runtime") == runtime_id \
                        and provider.get("binding_status") == "UNSERVED_RETAINED_PENDING_DECISION":
                    # Not a failure: only SERVED would be. Recorded for audit.
                    pass

    if _errors:
        return _report("MODEL_REGISTRY_INTEGRITY_FAIL", " | ".join(_errors[:12]))

    print(
        "MODEL_REGISTRY_INTEGRITY_PASS "
        f"providers={len(providers)} models={len(models)} "
        f"runtimes={len(runtimes)} processLibraries={len(process_libs)} "
        f"externalAssets={len(external_assets)} served_bindings={served_bindings}"
    )
    return 0


def _report(reason: str, detail: str) -> int:
    print(f"{reason} {detail}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--root", type=Path, default=default_root,
                        help="repository root to verify")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"MODEL_REGISTRY_INTEGRITY_ENV_ERROR root not a directory: {root}", file=sys.stderr)
        return 2
    return verify(root)


if __name__ == "__main__":
    raise SystemExit(main())

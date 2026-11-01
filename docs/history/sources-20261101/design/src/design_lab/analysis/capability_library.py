# SPDX-License-Identifier: MIT
"""DL-UI-PLAN: project the existing capability records into one read-only library view.

The library is assembled from documents the repository already maintains and gates;
nothing here discovers, installs, qualifies or downloads a capability:

* ``vendor/sources.lock.json``       - the 46 SourceRecords (license, disposition,
  presence, content digest, observation date);
* ``vendor/sources.revisions.json``  - commit revisions recovered by exact
  repository-path join, plus the explicitly unresolved set;
* ``design-lab/readiness/model-radar.json`` - model presence vs claim, with a
  five-stage state vocabulary.

Three rules the tests pin, because they are the failure modes this project keeps
hitting: an absent revision is ``NOT_VERIFIED`` and never "no provenance"; a
capability that has not been qualified reports ``qualified = None`` rather than
``False`` or a score; and every count is derived from the records in this call,
so a stale number cannot be hardcoded into the projection.
"""
from __future__ import annotations

import json
from pathlib import Path
from importlib.resources import files

SCHEMA_VERSION = "design-lab/capability-library/v1"
LOCK_REL = Path("vendor") / "sources.lock.json"
REVISIONS_REL = Path("vendor") / "sources.revisions.json"
RADAR_REL = Path("design-lab") / "readiness" / "model-radar.json"
TAXONOMY_REL = Path("research") / "candidates" / "CANDIDATE-TAXONOMY.json"

#: Axes the taxonomy schema declares but has never received a value for. They are
#: reported as unclassified rather than hidden, because a hidden column is how an
#: absent human judgement starts to look like a completed one.
CLASSIFICATION_AXES = ("domains", "artifactTypes", "capabilityLayers",
                       "aestheticAxes", "styleArchetypes", "tier", "designQuality")


def _repo_key(url: str | None) -> str:
    """Normalise to `owner/repo` for an exact join. No fuzzy or name matching:
    the revision record's own method field sets that rule and it holds here too."""
    value = (url or "").strip().lower().rstrip("/")
    for prefix in ("https://", "http://", "git+", "ssh://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    for prefix in ("github.com/", "gitlab.com/", "gitee.com/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.removesuffix(".git")


def _taxonomy_index(root: Path) -> dict:
    """candidateId-by-repo-key from the observation taxonomy, or {} when absent."""
    path = root / TAXONOMY_REL
    if not path.is_file():
        return {}
    index = {}
    for entry in _read_json(path).get("entries", []):
        for field in ("canonicalRepo", "canonicalUrl"):
            key = _repo_key(entry.get(field))
            if key:
                index.setdefault(key, entry)
    return index

#: Qualification is a host run plus a human acceptance outcome. Neither is
#: derivable from a registry, so the field is null until one is recorded.
#: UNQUALIFIED is the *value of an absent record*, not a constant the projection
#: writes for every row: `_qualification` looks the record up first, so a recorded
#: qualification reaches the UI without any further change (DL-FINAL-T06).
UNQUALIFIED = None

#: What a reader must be shown when the record is absent. "null" alone invites the
#: two wrong readings the task card names: not qualified, and not "0 of them".
NO_QUALIFICATION_RECORD = ("没有资格记录：需要该能力在已安装宿主上的真实运行，"
                           "加上真人对该版本产物结论的接受；两者都未记录时为 null")


def _qualification(candidate: dict | None) -> dict:
    """Project a recorded qualification, or say which evidence is missing.

    The record shape is `{"qualified": bool, "evidence": [ref, ...]}` on the joined
    taxonomy entry. Nothing in the repository carries one today, so every row reads
    back null with the reason attached -- which is a readback of an absent record,
    not a hardcoded verdict.
    """
    record = (candidate or {}).get("qualification")
    if not isinstance(record, dict):
        return {"qualified": UNQUALIFIED, "qualificationEvidence": None,
                "qualificationReason": NO_QUALIFICATION_RECORD}
    verdict = record.get("qualified")
    evidence = record.get("evidence")
    return {
        "qualified": verdict if isinstance(verdict, bool) else UNQUALIFIED,
        "qualificationEvidence": evidence if isinstance(evidence, list) else None,
        "qualificationReason": None if isinstance(verdict, bool) else (
            '记录存在但判定未填：' + NO_QUALIFICATION_RECORD),
    }


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"capability library input missing: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _source_capability(entry: dict, revisions: dict, unresolved: dict,
                       taxonomy: dict, repo_for_id: dict) -> dict:
    identity = str(entry.get("id", ""))
    pinned = revisions.get(identity)
    if pinned:
        state, revision = "VERIFIED", pinned.get("revision")
    elif identity in unresolved:
        state, revision = "UNRESOLVED", None
    else:
        # The revisions file's own meaning field says this: absence from `sources`
        # means NOT VERIFIED, never absence of provenance.
        state, revision = "NOT_VERIFIED", None
    return {
        "id": identity,
        "kind": "source",
        "domain": None,
        "title": entry.get("path") or identity,
        "disposition": entry.get("disposition"),
        "license": entry.get("license"),
        "presence": entry.get("presence"),
        "url": entry.get("canonicalUrl") or entry.get("url"),
        "revision": revision,
        "revisionState": state,
        "revisionReason": unresolved.get(identity),
        "repo": (pinned or {}).get("repo"),
        "observedAt": entry.get("observedAt"),
        "contentDigest": entry.get("contentDigest"),
        **_qualification(taxonomy.get(_repo_key(repo_for_id.get(identity)))),
        **_taxonomy_axes(taxonomy.get(_repo_key(repo_for_id.get(identity)))),
    }


def _taxonomy_axes(candidate: dict | None) -> dict:
    """The axes a joined taxonomy entry actually carries, plus what it does not.

    `evidenceLevel` and `rights` are real observations; `adoption` is popularity and is
    labelled as such because the taxonomy policy states popularityIsNotQuality. The
    classification axes are surfaced as null when unpopulated rather than defaulted.

    `axes` is the passthrough DL-FINAL-T06 asks for: the **values**, per axis, for the
    candidates that do carry one. `unclassifiedAxes` alone only answers "which are
    empty", so a populated axis reached the UI as nothing at all -- the counts and the
    empty list could both be right while a real classification stayed invisible.
    """
    if not candidate:
        return {"sourceType": None, "evidenceLevel": None, "upstreamOwner": None,
                "licenseUrl": None, "rightsNotes": None, "removalPath": None,
                "popularity": None, "unclassifiedAxes": list(CLASSIFICATION_AXES),
                "axes": {axis: None for axis in CLASSIFICATION_AXES}}
    rights = candidate.get("rights") or {}
    adoption = candidate.get("adoption") or {}
    metrics = adoption.get("metrics") or {}
    axes = [axis for axis in CLASSIFICATION_AXES if not candidate.get(axis)]
    return {
        "sourceType": candidate.get("sourceType"),
        "evidenceLevel": candidate.get("evidenceLevel"),
        "upstreamOwner": candidate.get("upstreamOwner"),
        "licenseUrl": rights.get("licenseURL"),
        "rightsNotes": rights.get("rightsNotes"),
        "removalPath": candidate.get("removalPath"),
        "popularity": {
            "stargazerCount": metrics.get("stargazerCount"),
            "forkCount": metrics.get("forkCount"),
            "observedAt": adoption.get("observedAt"),
            "source": adoption.get("source"),
            "isNotQuality": True,
        },
        "unclassifiedAxes": axes,
        "axes": {axis: candidate.get(axis) for axis in CLASSIFICATION_AXES},
    }


def _model_capability(entry: dict) -> dict:
    source = entry.get("source") or {}
    return {
        "id": str(entry.get("model_id", "")),
        "kind": "model",
        "domain": entry.get("family"),
        "title": entry.get("model_id"),
        "disposition": entry.get("radar_state"),
        "license": source.get("license_id"),
        "presence": entry.get("machine_state"),
        "url": None,
        "revision": None,
        # A model's revision is not tracked by the vendor mechanism; saying
        # NOT_VERIFIED keeps the vocabulary consistent instead of inventing one.
        "revisionState": "NOT_VERIFIED",
        "revisionReason": None,
        "repo": None,
        "observedAt": entry.get("observed_at"),
        "contentDigest": None,
        # A model row has no joined taxonomy entry, so the qualification lookup runs
        # against nothing: null plus the reason, never a defaulted false.
        **_qualification(None),
        # Every record carries the same keys, whichever kind it is: a missing axis on a
        # model row must read as unclassified, not as an absent field the view has to
        # special-case.
        **_taxonomy_axes(None),
    }


#: The three inputs are repository-committed records, not per-project or machine-local
#: state, so the library reads them from the package's own repository root. Resolving
#: them from a service project root would make the route depend on whichever synthetic
#: tree a harness happened to boot.
REPO_ROOT = Path(__file__).resolve().parents[3]


def build(root: Path | None = None) -> dict:
    """Return the capability library projection for one repository root."""
    if root is None:
        # Packaged first, repository second. REPO_ROOT is three levels up from this
        # file, which is the checkout in development and `<venv>/Lib` in an
        # installed wheel -- so without this branch the library only ever worked
        # from a source checkout while looking like a product feature.
        packaged = files("design_lab").joinpath("resources", "capability-library")
        root = packaged if packaged.joinpath(LOCK_REL).is_file() else REPO_ROOT
    else:
        root = Path(root)
    lock = _read_json(root / LOCK_REL)
    revisions = _read_json(root / REVISIONS_REL)
    radar = _read_json(root / RADAR_REL)
    pinned = revisions.get("sources") or {}
    unresolved = {str(item.get("id")): item.get("reason")
                  for item in (revisions.get("unresolved") or [])}

    taxonomy = _taxonomy_index(root)
    repo_for_id = {str(k): (v or {}).get("repo") for k, v in pinned.items()}
    capabilities = [_source_capability(entry, pinned, unresolved, taxonomy, repo_for_id)
                    for entry in lock.get("sources", [])]
    capabilities += [_model_capability(entry) for entry in radar.get("entries", [])]

    def tally(field: str) -> dict:
        counts: dict[str, int] = {}
        for item in capabilities:
            key = str(item.get(field))
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    unclassified = sorted({axis for c in capabilities for axis in c.get("unclassifiedAxes", [])})
    return {
        "schemaVersion": SCHEMA_VERSION,
        "classification": {
            "joined": sum(1 for c in capabilities if c.get("sourceType")),
            "unclassifiedAxes": unclassified,
            "note": ("These axes are declared by the candidate taxonomy and empty for "
                     "every observed candidate; filling them is a human classification "
                     "task, not a UI one."),
        },
        "meaning": ("Read-only projection of the source lock, the vendor revision "
                    "record and the model radar. It never installs, qualifies, "
                    "licenses or runs anything."),
        "unmeasuredMeans": ("null = not measured or not adjudicated. It is not 0, "
                            "not false and not 'none'. qualified=null means no host "
                            "run and no human acceptance exists yet."),
        "counts": {
            "total": len(capabilities),
            "joinedToTaxonomy": sum(1 for c in capabilities if c.get("sourceType")),
            "byKind": tally("kind"),
            "byLicense": tally("license"),
            "byRevisionState": tally("revisionState"),
            # Four numbers, because one key could only ever answer one of the two questions and it
            # read like the other: a page that shows "合格 0" for a library where nothing has ever
            # been judged is technically true and practically a claim. A verdict requires a host run
            # plus a human acceptance, which no registry in this repository can yield.
            "qualificationVerdicts": sum(1 for c in capabilities
                                         if isinstance(c["qualified"], bool)),
            "qualifiedTrue": sum(1 for c in capabilities if c["qualified"] is True),
            "qualifiedFalse": sum(1 for c in capabilities if c["qualified"] is False),
            "qualificationNotAdjudicated": sum(1 for c in capabilities
                                               if c["qualified"] is None),
        },
        "sources": {"lock": LOCK_REL.as_posix(), "revisions": REVISIONS_REL.as_posix(),
                    "radar": RADAR_REL.as_posix()},
        "capabilities": capabilities,
    }

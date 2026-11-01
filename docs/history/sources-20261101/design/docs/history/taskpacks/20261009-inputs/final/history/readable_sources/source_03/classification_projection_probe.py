"""Isolated probe of the inspected DESIGN-LAB classification projection.

Source: DTALEX66/DESIGN-LAB @ fc03a3033e900a8066d863a223636cc68804c4fa
File: src/design_lab/analysis/capability_library.py
Scope: extracted function only; NOT a repository test or installed-app test.
The function body and CLASSIFICATION_AXES below are transcribed from the source.
"""
import json
from pathlib import Path

CLASSIFICATION_AXES = ("domains", "artifactTypes", "capabilityLayers",
                       "aestheticAxes", "styleArchetypes", "tier", "designQuality")


def _taxonomy_axes(candidate: dict | None) -> dict:
    """The axes a joined taxonomy entry actually carries, plus what it does not.

    `evidenceLevel` and `rights` are real observations; `adoption` is popularity and is
    labelled as such because the taxonomy policy states popularityIsNotQuality. The
    classification axes are surfaced as null when unpopulated rather than defaulted.
    """
    if not candidate:
        return {"sourceType": None, "evidenceLevel": None, "upstreamOwner": None,
                "licenseUrl": None, "rightsNotes": None, "removalPath": None,
                "popularity": None, "unclassifiedAxes": list(CLASSIFICATION_AXES)}
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
    }


def main() -> None:
    # Synthetic values exercise the projection. They are not reviews or quality
    # assessments of any real source, and do not write to a project registry.
    candidate = {key: ["synthetic-filled-value"] for key in CLASSIFICATION_AXES}
    candidate.update(sourceType="synthetic", evidenceLevel="E0")
    actual = _taxonomy_axes(candidate)
    missing = [key for key in CLASSIFICATION_AXES if key not in actual]
    assert actual["unclassifiedAxes"] == []
    assert missing == list(CLASSIFICATION_AXES)
    result = {
        "source_sha": "fc03a3033e900a8066d863a223636cc68804c4fa",
        "source_file": "src/design_lab/analysis/capability_library.py",
        "scope": "ISOLATED_TRANSCRIBED_FUNCTION_NOT_FULL_REPO_OR_INSTALLED_APP",
        "input_axes_populated": list(CLASSIFICATION_AXES),
        "output_unclassified_axes": actual["unclassifiedAxes"],
        "populated_axes_absent_from_output": missing,
        "verdict": "CLASSIFICATION_VALUES_ARE_NOT_PROJECTED",
        "limitations": [
            "Synthetic fixture, not live candidate data.",
            "Does not execute the application, browser, wheel, or a real host.",
            "No full-repository checkout or tests were performed."
        ]
    }
    path = Path(__file__).with_name("classification_projection_probe_result.json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

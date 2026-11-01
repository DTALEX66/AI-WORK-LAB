# SPDX-License-Identifier: MIT
"""DL-P1-130: OTIO timeline contract, exact plan round trip and layout reports (E1 structural)."""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.interop import InteropError  # noqa: E402
from design_lab.interop import timeline  # noqa: E402

SCHEMA_PATH = ROOT / "design-lab/schemas/interop-timeline-otio.schema.json"


def external_clip(name: str, target: str, duration: float) -> dict:
    return {
        "OTIO_SCHEMA": "Clip.1",
        "name": name,
        "metadata": {},
        "source_range": timeline.time_range(0.0, duration, 24),
        "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": target,
                            "available_range": None, "metadata": {}},
    }


def transition_timeline() -> dict:
    """A one-track timeline whose two clips are joined by a dissolve."""
    track = {
        "OTIO_SCHEMA": "Track.1",
        "name": "V1",
        "kind": "Video",
        "metadata": {},
        "source_range": None,
        "children": [
            external_clip("A", "asset://take-a", 2.0),
            {"OTIO_SCHEMA": "Transition.1", "name": "dissolve",
             "transition_type": "SMPTE_Dissolve",
             "in_offset": timeline.rational_time(0.25, 24),
             "out_offset": timeline.rational_time(0.5, 24)},
            external_clip("B", "asset://take-b", 3.0),
        ],
    }
    return {
        "OTIO_SCHEMA": "Timeline.1",
        "name": "transition-demo",
        "global_start_time": None,
        "metadata": {},
        "tracks": {"OTIO_SCHEMA": "Stack.1", "name": "tracks", "metadata": {},
                   "children": [track]},
    }


def demo_plan() -> dict:
    return {
        "name": "dl-demo",
        "metadata": {"brief": "DL-P1-130 fixture"},
        "global_start_time_seconds": 1.5,
        "tracks": [
            {"name": "V1", "kind": "Video", "metadata": {"role": "hero"}, "clips": [
                {"clip_id": "clip-b", "asset_ref": "asset://take-b", "start_seconds": 8.25,
                 "duration_seconds": 2.0, "rate": 24, "metadata": {"note": "second"}},
                {"clip_id": "clip-a", "asset_ref": "asset://take-a", "start_seconds": 0.5,
                 "duration_seconds": 3.5, "rate": 24, "metadata": {}},
                {"clip_id": "clip-c", "asset_ref": "asset://take-a", "start_seconds": 12.3456789,
                 "duration_seconds": 1.25, "rate": 24, "metadata": {}},
            ]},
            {"name": "A1", "kind": "Audio", "metadata": {}, "clips": [
                {"clip_id": "aud-1", "asset_ref": "asset://music", "start_seconds": 0.0,
                 "duration_seconds": 14.0, "rate": 48000, "metadata": {}},
            ]},
        ],
    }


class TimelineFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = ROOT / ".project-local/task-runtime/interop-timeline-tests"
        parent.mkdir(parents=True, exist_ok=True)
        cls._temp = tempfile.TemporaryDirectory(dir=parent)
        cls.addClassCleanup(cls._temp.cleanup)
        cls.workdir = Path(cls._temp.name)
        cls.document = timeline.to_timeline(demo_plan())


class TimelineContractTest(TimelineFixture):
    def test_module_declares_the_interchange_boundary(self):
        self.assertEqual(timeline.OTIO_SCHEMA_VERSION, "Timeline.1")
        self.assertEqual(timeline.TIMELINE_SCHEMA, "Timeline.1")
        docstring = timeline.__doc__ or ""
        self.assertIn("DESIGN-LAB does not own video rendering", docstring)
        self.assertIn("interchange format", docstring)
        self.assertIn("round(value / rate, 9)", docstring)

    def test_module_imports_no_otio_library(self):
        source = Path(timeline.__file__).read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*(?:import|from)\s+opentimelineio", source, re.M))

    def test_schema_is_repo_owned_draft_2020_12(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"],
                         "https://dtalex66.local/schemas/interop-timeline-otio.schema.json")

    def test_generated_document_validates_and_reports_layout(self):
        report = timeline.validate_timeline(self.document)
        self.assertEqual(report["track_count"], 2)
        self.assertEqual(report["track_kinds"], ["Audio", "Video"])
        self.assertEqual(report["clip_count"], 4)
        self.assertEqual(report["gap_count"], 3)
        self.assertEqual(report["transition_count"], 0)
        self.assertEqual(report["declared_ids"], ["aud-1", "clip-a", "clip-b", "clip-c"])
        self.assertEqual(report["duration_seconds"], 14.0)
        # V1 and A1 are stacked tracks: OTIO lays them out in parallel, so they
        # genuinely overlap up to the shorter track's end. There are no transitions.
        self.assertEqual(report["overlaps"], [{
            "reason": "parallel-stack", "a": "V1", "b": "A1",
            "overlap_seconds": 13.5956789,
            "where": "timeline.tracks[0] + timeline.tracks[1]",
        }])

    def test_document_survives_a_disk_round_trip(self):
        target = self.workdir / "timeline.otio"
        target.write_text(json.dumps(self.document, ensure_ascii=False, indent=2), encoding="utf-8")
        reloaded = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(timeline.from_timeline(reloaded), timeline.from_timeline(self.document))

    def test_gaps_preserve_the_plan_layout(self):
        children = self.document["tracks"]["children"][0]["children"]
        kinds = [child["OTIO_SCHEMA"] for child in children]
        self.assertEqual(kinds, ["Gap.1", "Clip.1", "Gap.1", "Clip.1", "Gap.1", "Clip.1"])
        first_gap = timeline.seconds_from(children[0]["source_range"]["duration"])
        self.assertEqual(first_gap, 0.5)
        self.assertEqual(children[1]["metadata"]["design_lab"]["clip_id"], "clip-a")
        self.assertEqual(children[1]["media_reference"]["target_url"], "asset://take-a")

    def test_rational_time_rounds_only_at_nanosecond_resolution(self):
        for seconds, rate in ((0.2, 24), (12.3456789, 24), (1.5, 30), (0.0, 1000), (3.333333333, 30)):
            with self.subTest(seconds=seconds, rate=rate):
                self.assertEqual(timeline.seconds_from(timeline.rational_time(seconds, rate)), seconds)

    def test_negative_or_zero_rate_fails_closed(self):
        with self.assertRaises(InteropError):
            timeline.rational_time(1.0, 0)
        with self.assertRaises(InteropError):
            timeline.seconds_from({"OTIO_SCHEMA": "RationalTime.1", "rate": -24, "value": 1})

    def test_track_kind_is_restricted(self):
        document = json.loads(json.dumps(self.document))
        document["tracks"]["children"][0]["kind"] = "Subtitle"
        with self.assertRaises(InteropError) as caught:
            timeline.validate_timeline(document)
        self.assertIn("Subtitle", str(caught.exception))

    def test_track_cannot_appear_inside_a_track(self):
        document = json.loads(json.dumps(self.document))
        track = document["tracks"]["children"][0]
        track["children"].append(json.loads(json.dumps(track)))
        with self.assertRaises(InteropError) as caught:
            timeline.validate_timeline(document)
        self.assertIn("interop-timeline-otio.schema.json", str(caught.exception))

    def test_duplicate_design_lab_ids_fail_closed(self):
        document = json.loads(json.dumps(self.document))
        document["tracks"]["children"][1]["children"][0]["metadata"]["design_lab"]["clip_id"] = "clip-a"
        with self.assertRaises(InteropError) as caught:
            timeline.validate_timeline(document)
        self.assertIn("duplicate DESIGN-LAB id", str(caught.exception))

    def test_gap_without_source_range_fails_closed(self):
        document = json.loads(json.dumps(self.document))
        gap = document["tracks"]["children"][0]["children"][0]
        del gap["source_range"]
        with self.assertRaises(InteropError) as caught:
            timeline.validate_timeline(document)
        # The structural schema rejects the gap first; the Python rule is defence in depth.
        self.assertIn("tracks/children/0/children/0", str(caught.exception))

    def test_wrong_timeline_schema_fails_closed(self):
        document = json.loads(json.dumps(self.document))
        document["OTIO_SCHEMA"] = "Timeline.2"
        with self.assertRaises(InteropError):
            timeline.validate_timeline(document)

    def test_unknown_top_level_key_fails_closed(self):
        document = json.loads(json.dumps(self.document))
        document["extra"] = 1
        with self.assertRaises(InteropError) as caught:
            timeline.validate_timeline(document)
        self.assertIn("interop-timeline-otio.schema.json", str(caught.exception))


class TimelineRoundTripTest(TimelineFixture):
    def test_plan_round_trip_is_exact(self):
        plan = demo_plan()
        self.assertEqual(timeline.roundtrip(plan), timeline.canonical_plan(plan))
        self.assertEqual(timeline.roundtrip(plan), timeline.canonical_plan(timeline.roundtrip(plan)))

    def test_canonical_plan_orders_clips_by_layout(self):
        canonical = timeline.canonical_plan(demo_plan())
        video = canonical["tracks"][0]
        self.assertEqual([clip["clip_id"] for clip in video["clips"]], ["clip-a", "clip-b", "clip-c"])
        self.assertEqual([clip["start_seconds"] for clip in video["clips"]], [0.5, 8.25, 12.3456789])

    def test_sparse_plan_round_trips_to_its_canonical_form(self):
        sparse = {"tracks": [{"kind": "Video", "clips": [
            {"clip_id": "c1", "asset_ref": "asset://a", "start_seconds": 1.0,
             "duration_seconds": 2.0},
        ]}]}
        self.assertEqual(timeline.roundtrip(sparse), timeline.canonical_plan(sparse))

    def test_metadata_round_trips_without_the_reserved_key(self):
        plan = timeline.canonical_plan(demo_plan())
        rebuilt = timeline.roundtrip(plan)
        self.assertEqual(rebuilt["tracks"][0]["metadata"], {"role": "hero"})
        self.assertEqual(rebuilt["tracks"][0]["clips"][1]["metadata"], {"note": "second"})
        self.assertEqual(rebuilt["metadata"], {"brief": "DL-P1-130 fixture"})

    def test_plan_may_not_use_the_reserved_metadata_key(self):
        plan = demo_plan()
        plan["metadata"] = {"design_lab": {"clip_id": "x"}}
        with self.assertRaises(InteropError) as caught:
            timeline.to_timeline(plan)
        self.assertIn("reserved key", str(caught.exception))

    def test_overlapping_plan_clips_fail_closed(self):
        plan = demo_plan()
        plan["tracks"][0]["clips"].append({
            "clip_id": "clip-overlap", "asset_ref": "asset://take-a", "start_seconds": 1.0,
            "duration_seconds": 1.0, "rate": 24, "metadata": {}})
        with self.assertRaises(InteropError) as caught:
            timeline.to_timeline(plan)
        self.assertIn("no overlap concept", str(caught.exception))

    def test_duplicate_clip_ids_fail_closed(self):
        plan = demo_plan()
        plan["tracks"][1]["clips"].append(dict(plan["tracks"][1]["clips"][0]))
        with self.assertRaises(InteropError) as caught:
            timeline.to_timeline(plan)
        self.assertIn("more than once", str(caught.exception))

    def test_transitions_and_stacks_cannot_be_silently_dropped(self):
        document = json.loads(json.dumps(self.document))
        transition = {"OTIO_SCHEMA": "Transition.1", "name": "dissolve",
                      "transition_type": "SMPTE_Dissolve",
                      "in_offset": timeline.rational_time(0.25, 24),
                      "out_offset": timeline.rational_time(0.25, 24)}
        document["tracks"]["children"][0]["children"].insert(2, transition)
        with self.assertRaises(InteropError) as caught:
            timeline.from_timeline(document)
        self.assertIn("no transition concept", str(caught.exception))

        nested = json.loads(json.dumps(self.document))
        stack = {"OTIO_SCHEMA": "Stack.1", "name": "layers", "metadata": {},
                 "children": [external_clip("layer", "asset://layer", 1.0)]}
        nested["tracks"]["children"][0]["children"].append(stack)
        with self.assertRaises(InteropError) as caught:
            timeline.from_timeline(nested)
        self.assertIn("nested Stack.1", str(caught.exception))

    def test_clip_without_source_range_is_unresolvable(self):
        document = json.loads(json.dumps(self.document))
        document["tracks"]["children"][0]["children"][1]["source_range"] = None
        with self.assertRaises(InteropError) as caught:
            timeline.validate_timeline(document)
        self.assertIn("available_range", str(caught.exception))


class TimelineLayoutTest(TimelineFixture):
    def test_duration_of_a_track_sequences_and_of_a_stack_maxes(self):
        video = self.document["tracks"]["children"][0]
        self.assertEqual(timeline.duration_seconds(video), 13.5956789)
        self.assertEqual(timeline.duration_seconds(self.document), 14.0)
        stack = {"OTIO_SCHEMA": "Stack.1", "name": "layers", "metadata": {}, "children": [
            video,
            {"OTIO_SCHEMA": "Gap.1", "source_range": timeline.time_range(0.0, 2.0, 24), "metadata": {}},
        ]}
        self.assertEqual(timeline.duration_seconds(stack), 13.5956789)

    def test_transition_overlap_follows_the_official_covered_range(self):
        document = transition_timeline()
        report = timeline.validate_timeline(document)
        self.assertEqual(report["transition_count"], 1)
        # A is 2.0s and B is 3.0s; in_offset=0.25, out_offset=0.5, so the transition
        # starts at the 2.0s cut and covers [1.75, 2.5]: 0.25s inside A, 0.5s inside B.
        self.assertEqual(report["overlaps"], [
            {
                "reason": "transition", "a": "A", "b": "dissolve", "covered_side": "in_offset",
                "in_offset_seconds": 0.25, "out_offset_seconds": 0.5,
                "transition_start_seconds": 2.0,
                "covered_start_seconds": 1.75, "covered_end_seconds": 2.5,
                "overlap_seconds": 0.25, "where": "timeline.tracks[0][1]",
            },
            {
                "reason": "transition", "a": "B", "b": "dissolve", "covered_side": "out_offset",
                "in_offset_seconds": 0.25, "out_offset_seconds": 0.5,
                "transition_start_seconds": 2.0,
                "covered_start_seconds": 1.75, "covered_end_seconds": 2.5,
                "overlap_seconds": 0.5, "where": "timeline.tracks[0][1]",
            },
        ])

    def test_covered_range_is_clamped_to_the_neighbouring_item(self):
        # in_offset reaches past the whole 1.0s clip A: the covered range still
        # starts at A's own start, so the overlap cannot exceed A's duration.
        document = transition_timeline()
        track = document["tracks"]["children"][0]
        track["children"][0]["source_range"] = timeline.time_range(0.0, 1.0, 24)
        track["children"][1]["in_offset"] = timeline.rational_time(4.0, 24)
        records = timeline.overlaps(document)
        self.assertEqual([record["overlap_seconds"] for record in records], [1.0, 0.5])
        self.assertEqual(records[0]["covered_start_seconds"], -3.0)

    def test_the_formula_is_documented_in_the_module(self):
        self.assertIn("transition_start - in_offset", timeline.TRANSITION_COVERED_RANGE)
        docstring = timeline.__doc__ or ""
        self.assertIn("transition_start - in_offset", docstring)
        self.assertIn("transition_start + out_offset", docstring)
        self.assertIn("covered_range", timeline.overlaps.__doc__ or "")

    def test_negative_transition_offsets_and_adjacent_transitions_fail_closed(self):
        document = transition_timeline()
        document["tracks"]["children"][0]["children"][1]["in_offset"] = (
            timeline.rational_time(-0.25, 24))
        with self.assertRaises(InteropError) as caught:
            timeline.validate_timeline(document)
        self.assertIn("must not be negative", str(caught.exception))

        doubled = transition_timeline()
        children = doubled["tracks"]["children"][0]["children"]
        children.insert(2, json.loads(json.dumps(children[1])))
        with self.assertRaises(InteropError) as caught:
            timeline.overlaps(doubled)
        self.assertIn("next to another Transition.1", str(caught.exception))

    def test_parallel_stack_children_overlap(self):
        stack = {"OTIO_SCHEMA": "Stack.1", "name": "layers", "metadata": {}, "children": [
            {"OTIO_SCHEMA": "Gap.1", "name": "g1",
             "source_range": timeline.time_range(0.0, 4.0, 24), "metadata": {}},
            {"OTIO_SCHEMA": "Gap.1", "name": "g2",
             "source_range": timeline.time_range(0.0, 2.5, 24), "metadata": {}},
        ]}
        self.assertEqual(timeline.overlaps(stack), [{
            "reason": "parallel-stack", "a": "g1", "b": "g2", "overlap_seconds": 2.5,
            "where": "stack[0] + stack[1]",
        }])
        self.assertEqual(timeline.overlaps(self.document["tracks"]["children"][0]), [])

    def test_transition_at_a_track_boundary_fails_closed(self):
        document = json.loads(json.dumps(self.document))
        document["tracks"]["children"][0]["children"].insert(0, {
            "OTIO_SCHEMA": "Transition.1", "name": "bad", "transition_type": "SMPTE_Dissolve",
            "in_offset": timeline.rational_time(0.25, 24),
            "out_offset": timeline.rational_time(0.25, 24)})
        with self.assertRaises(InteropError) as caught:
            timeline.validate_timeline(document)
        self.assertIn("track boundary", str(caught.exception))


class TimelineAssetTest(TimelineFixture):
    def test_declared_assets_are_checked(self):
        report = timeline.validate_against_assets(
            self.document, ["asset://take-a", "asset://take-b", "asset://music", "asset://unused"])
        self.assertEqual(report["clip_count"], 4)
        self.assertEqual(report["declared_asset_count"], 4)
        self.assertEqual(report["referenced_assets"], ["asset://music", "asset://take-a", "asset://take-b"])
        self.assertEqual(report["unused_assets"], ["asset://unused"])
        self.assertEqual(report["clips_per_asset"]["asset://take-a"], 2)

    def test_undeclared_asset_fails_closed(self):
        with self.assertRaises(InteropError) as caught:
            timeline.validate_against_assets(self.document, ["asset://take-a", "asset://take-b"])
        self.assertIn("undeclared asset", str(caught.exception))
        self.assertIn("asset://music", str(caught.exception))

    def test_offline_and_missing_media_references_fail_closed(self):
        declared = ["asset://take-a", "asset://take-b"]
        document = json.loads(json.dumps(self.document))
        clip = document["tracks"]["children"][1]["children"][0]
        clip["media_reference"] = {"OTIO_SCHEMA": "MissingReference.1", "metadata": {}}
        with self.assertRaises(InteropError) as caught:
            timeline.validate_against_assets(document, declared)
        self.assertIn("MissingReference.1", str(caught.exception))

        del clip["media_reference"]
        with self.assertRaises(InteropError) as caught:
            timeline.validate_against_assets(document, declared)
        self.assertIn("undeclared", str(caught.exception))

    def test_empty_declaration_fails_closed(self):
        with self.assertRaises(InteropError):
            timeline.validate_against_assets(self.document, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

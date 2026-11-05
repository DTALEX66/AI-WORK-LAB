"""Guards for ``scripts/measure_citation_population.py`` -- the tool two entry numbers came from.

This project has now published two wrong figures of exactly this kind: a "322 tracked files carry the
machine account name" that also counted the public repo owner ``DTALEX66`` (same letters), and a
"621 prose ``.py:line`` cites" produced by a script that quietly skipped ``docs/history/`` -- 860 of
the real 1482 cites, silently, which is a truncated listing read as an absence. So the tool is
tracked, and these nodes are what keep it honest: the ownership rule is checked at prefix boundaries
(a copied tree must not claim ``domains/design_lab``, and ``AGENTS.md`` is not a copy of anything), the
account pattern must not fire on the repo-owner token, a missing ledger or an undeterminable account
name must abort rather than return a reassuring zero, and the bucket sums must equal the totals the
entry quotes.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

TARGET_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = TARGET_ROOT / "scripts" / "measure_citation_population.py"


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location("measure_citation_population_live", SCRIPT)
    document = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = document
    spec.loader.exec_module(document)
    return document


def test_ownership_is_decided_at_prefix_boundaries_not_by_a_suffix(module):
    """The rule that made ``AGENTS.md`` look like a migrated copy, fixed and then pinned."""
    claimed = {"domains/design", "domains/design/design_lab/runtime/paths.py"}
    assert module.owner_of("domains/design/thing.py", claimed) == "migrated_copy"
    assert module.owner_of("domains/design/design_lab/runtime/paths.py", claimed) == "migrated_copy"
    # a sibling whose name merely starts with the same letters is NOT inside the copied tree
    assert module.owner_of("domains/design_lab/other.py", claimed) != "migrated_copy", (
        "prefix matching without a boundary swallowed a sibling tree -- the same defect that would"
        " have made a source-record count look smaller than it is")
    # and a root file ending in the same text as a ledger entry is not that entry
    assert module.owner_of("AGENTS.md", claimed | {"design-lab/AGENTS.md"}) != "migrated_copy", (
        "an endswith-style match claimed this repo's own root instruction file as a source copy")
    assert module.owner_of("backend/v1.py", set()) == "own_code_and_checks"
    assert module.owner_of("migration/copies.json", set()) == "generated_register"
    assert module.owner_of("docs/CODEX-AUDIT-ENTRY.md", set()) == "append_only_history"
    assert module.owner_of("docs/authority-202610/anything.md", set()) == "frozen_source_input"


def test_the_repo_owner_token_is_not_an_account_mention(module, tmp_path):
    """``DTALEX66`` contains the account letters; counting it is what inflated 218 into 322."""
    (tmp_path / "owner.md").write_text("cloned from DTALEX66/AI-WORK-LAB\n", encoding="utf-8")
    (tmp_path / "paths.md").write_text("C:\\Users\\alex\\work\n", encoding="utf-8")
    (tmp_path / "bare.md").write_text("user alex signed off here\n", encoding="utf-8")
    document = module.measure(root=tmp_path, account="alex", claimed=set(),
                              files=["owner.md", "paths.md", "bare.md"])
    buckets = document["by_ownership"]
    total = {field: sum(buckets[key][field] for key in buckets)
             for field in ("account_mentions", "absolute_machine_paths")}
    assert total["account_mentions"] == 2, (
        "the repo-owner token was counted as an account mention again: %s" % buckets)
    assert total["absolute_machine_paths"] == 1, buckets
    assert document["totals"]["files"] == 2, buckets


def test_a_missing_ledger_aborts_instead_of_narrowing_the_scan(module, tmp_path, monkeypatch):
    """Zero looks like a clean bill of health; here an unreadable ledger must be a refusal."""
    with pytest.raises(SystemExit) as abort:
        module.measure(root=tmp_path, account="", claimed=set(), files=["x.py"])
    assert "MEASUREMENT_PREREQ_MISSING" in str(abort.value)

    missing = tmp_path / "nope"
    missing.mkdir()
    monkeypatch.setattr(module, "COPIES", missing / "copies.json")
    with pytest.raises(SystemExit) as abort:
        module.ledger_targets()
    assert "MEASUREMENT_LEDGER_ABSENT" in str(abort.value)

    (missing / "migration").mkdir()
    (missing / "migration" / "copies.json").write_text('{"copies": []}', encoding="utf-8")
    monkeypatch.setattr(module, "COPIES", missing / "migration" / "copies.json")
    monkeypatch.setattr(module, "MANIFEST", missing / "MANIFEST.csv")
    with pytest.raises(SystemExit) as abort:
        module.ledger_targets()
    assert "MEASUREMENT_LEDGER_ABSENT" in str(abort.value), (
        "the history MANIFEST is the second ownership source; dropping it silently would reclassify"
        " source records as our own prose and make a rewrite look authorised")

    # a ledger of the wrong shape is refused too -- a key typo is how claimed came back empty once
    (missing / "migration" / "copies.json").write_text('{"generated_at": "x"}', encoding="utf-8")
    monkeypatch.setattr(module, "MANIFEST", TARGET_ROOT / "docs" / "history" / "sources-20261101"
                        / "MANIFEST.csv")
    with pytest.raises(SystemExit) as abort:
        module.ledger_targets()
    assert "MEASUREMENT_LEDGER_SHAPE" in str(abort.value)


def test_the_published_totals_recompute_and_the_buckets_account_for_every_file(module):
    """The number quoted in the entry must be reproducible from the tool, and internally closed."""
    first = module.measure()
    second = module.measure()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True), (
        "the measurement is not deterministic, so no register may quote it")
    sums = {field: sum(bucket[field] for bucket in first["by_ownership"].values())
            for field in ("files", "line_cites", "account_mentions", "absolute_machine_paths")}
    assert sums == first["totals"], "bucketed counts do not add up to the published totals"
    assert first["files_scanned"] > 7000, first["files_scanned"]
    # the whole tree, with docs/history included -- the earlier instrument lost 860 cites that way
    assert first["by_ownership"]["frozen_source_input"]["line_cites"] > 800, (
        "docs/history/ stopped being counted; the entry's cite population just shrank by ~860"
        " without anyone saying so")
    # samples are capped per bucket, so inclusion is asserted by count and by the rule itself,
    # not by hoping a history path survives the cap
    assert module.owner_of("docs/history/sources-20261101/MANIFEST.csv", set()) == (
        "frozen_source_input")
    assert first["by_ownership"]["own_code_and_checks"]["line_cites"] > 0, (
        "the subset a guard may widen into is empty -- check the ownership prefixes")

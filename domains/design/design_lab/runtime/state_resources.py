# SPDX-License-Identifier: MIT
"""Resolve immutable SQL resources in an installed package or its source tree.

The source SQL directory remains authoritative. A distribution builder must
copy those bytes into resources/state; a missing installed resource fails closed.
"""
from importlib.resources import files
from pathlib import Path

_NAMES = frozenset({
    'design-lab-state-v1.sql',
    'design-lab-state-assets-v1.sql',
    'design-lab-state-assets-v2.sql',
    'design-lab-state-attempt-v1.sql',
    'design-lab-state-attempt-v2.sql',
    'design-lab-state-creative-v1.sql',
    'design-lab-state-jury-v1.sql',
    # 2026-10-08 quality-gate reachability: the sealed QualityRecord store
    # (design-lab/schemas/state/design-lab-state-quality-v1.sql, applied by
    # src/design_lab/assurance/quality_store.py). Additive: one new immutable
    # resource name, no existing file renamed or re-versioned.
    'design-lab-state-quality-v1.sql',
    # 2026-10-08 rights-gate reachability: the Human Rights decision store
    # (design-lab/schemas/state/design-lab-state-rights-v1.sql, applied by
    # src/design_lab/assurance/rights_ledger.py). Additive: one new immutable
    # resource name, no existing file renamed or re-versioned.
    'design-lab-state-rights-v1.sql',
    # 2026-10-08 research-finding reachability: the ResearchFinding working-state store
    # (design-lab/schemas/state/design-lab-state-research-v1.sql, applied by
    # src/design_lab/assurance/research_store.py). Additive: one new immutable resource
    # name, no existing file renamed or re-versioned.
    'design-lab-state-research-v1.sql',
    # 2026-10-18 U09/T16 knowledge-feedback reachability: the candidate revisions and
    # revocation receipts store (design-lab/schemas/state/design-lab-state-knowledge-v1.sql,
    # applied by src/design_lab/knowledge_review.py). Additive: one new immutable resource
    # name, no existing file renamed or re-versioned.
    'design-lab-state-knowledge-v1.sql',
    'design-lab-state-design-layer-v1.sql',
    'design-lab-state-design-layer-v2.sql',
    'design-lab-state-design-layer-v3.sql',
    'design-lab-state-design-layer-v4.sql',
    # 2026-10-20 model-selection reachability: the per-project record of an operator choosing a
    # model, or declining to (design-lab/schemas/state/design-lab-state-model-selection-v1.sql,
    # applied by src/design_lab/model_selection.py). Additive: one new immutable resource name, no
    # existing file renamed or re-versioned.
    'design-lab-state-model-selection-v1.sql',
    # 2026-10-22 prompt-result reachability: the stored prompt compositions and reversals, plus the
    # human acceptance that binds one of them (design-lab/schemas/state/
    # design-lab-state-prompt-results-v1.sql, applied by src/design_lab/prompt_results.py). Additive:
    # one new immutable resource name, no existing file renamed or re-versioned.
    'design-lab-state-prompt-results-v1.sql',
    # 2026-10-23 DL-KB-02 knowledge-library reachability: the entries a person wrote down, their
    # append-only revisions, and the derived FTS5 trigram index
    # (design-lab/schemas/state/design-lab-state-knowledge-library-v1.sql, applied by
    # src/design_lab/knowledge_library.py). Additive: one new immutable resource name, no existing
    # file renamed or re-versioned.
    'design-lab-state-knowledge-library-v1.sql',
    # 2026-10-24 DL-KB-05 D5 reachability: recorded judgements about an entry -- rolling the
    # recommendation back to an older revision, and marking a source invalid with its replacement
    # (design-lab/schemas/state/design-lab-state-knowledge-judgement-v1.sql, applied by
    # src/design_lab/knowledge_library.py). Additive: the revision rows stay append-only, so a
    # later judgement is a new row rather than an UPDATE of a stored document.
    'design-lab-state-knowledge-judgement-v1.sql',
    # 2026-10-24 DL-KB-07 assistance-plan reachability: the neutral design intent, its append-only
    # revisions and the named human's adoption record
    # (design-lab/schemas/state/design-lab-state-assistance-plan-v1.sql, applied by
    # src/design_lab/assistance_plan.py). Additive: one new immutable resource name, no existing
    # file renamed or re-versioned.
    'design-lab-state-assistance-plan-v1.sql',
    # 2026-10-24 DL-KB-09 target-profile reachability: the drafts a person adds at the selection
    # panel, append-only (design-lab/schemas/state/design-lab-state-target-profile-v1.sql, applied
    # by src/design_lab/target_profile.py). The five seeded profiles are NOT stored here -- they
    # are served from the tracked config, so one byte has one owner. Additive: one new immutable
    # resource name, no existing file renamed or re-versioned.
    'design-lab-state-target-profile-v1.sql',
    # 2026-10-24 DL-KB-16 plan-feedback reachability: the voluntary reports about taking a plan's
    # material to an external tool (design-lab/schemas/state/design-lab-state-plan-feedback-v1.sql,
    # applied by src/design_lab/plan_feedback.py). Additive: one new immutable resource name, no
    # existing file renamed or re-versioned.
    'design-lab-state-plan-feedback-v1.sql',
})


def state_schema(name):
    if name not in _NAMES:
        raise ValueError('unknown state schema resource')
    packaged = files('design_lab').joinpath('resources', 'state', name)
    if packaged.is_file():
        return packaged
    module = Path(__file__).resolve()
    root = module.parents[3]
    # Never search CWD, a user profile, or an unrelated adjacent project.
    if (root / 'src/design_lab/runtime/state_resources.py').resolve() == module:
        source = root / 'design-lab/schemas/state' / name
        if source.is_file():
            return source
    raise FileNotFoundError(f'packaged state schema missing: {name}')


def repo_resource(relative, packaged_root=('resources', 'repo'),
                  source_root=('design-lab',)):
    """Resolve a repository-committed file that a read path needs at runtime.

    ``relative`` keeps the repository's own spelling (``schemas/contracts/
    rights-decision.schema.json``, ``domain-packs/graphic-design``). Two layouts are
    consulted, in this order:

    1. the packaged copy under ``design_lab/resources/repo/<source_root>/<relative>``,
       which is what an installed wheel carries (pyproject force-include);
    2. this checkout's own tree, reached by walking up from this module -- and only
       when this module really is the checkout's copy, so an installed wheel can
       never fall back to a neighbouring unrelated directory.

    D09 (batch 22): contract readers used ``PROJECT_ROOT / ...``, and ``PROJECT_ROOT``
    is ``Path(__file__).parents[3]``. Three levels above ``src/design_lab/runtime`` is
    the checkout, but three levels above an installed ``site-packages/design_lab/
    runtime`` is ``Lib/`` -- so an installed wheel read a path that does not exist and
    the route answered 500 / MISSING instead of a real verdict.
    """
    packaged = files('design_lab').joinpath(*packaged_root, *source_root,
                                            *Path(relative).parts)
    if packaged.exists():
        return packaged
    module = Path(__file__).resolve()
    root = module.parents[3]
    if (root / 'src/design_lab/runtime/state_resources.py').resolve() == module:
        source = root.joinpath(*source_root, *Path(relative).parts)
        if source.exists():
            return source
    raise FileNotFoundError(f'packaged repository resource missing: {relative}')

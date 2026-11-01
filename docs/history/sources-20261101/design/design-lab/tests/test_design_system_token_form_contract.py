# SPDX-License-Identifier: MIT
"""The Workbench's token column may only declare fields the service really has.

``renderTokenDocumentPanel`` prints ``TOKEN_DOCUMENT_FIELDS`` and posts
``TOKEN_WRITE_FIELDS``; the service shapes its readback in
``design_layer.DesignLayer._token_document`` and validates the body against
``design_layer.TOKEN_WRITE_FIELDS``. Nothing connects the two, so a rename on
either side ships a column that prints ``undefined``, a form the route rejects as
INVALID_PROJECT_FIELDS, or -- the worse direction -- a page that quietly stops
showing a field the service kept writing.

Same shape as ``test_jury_review_form_contract.py``: read the page's own
declaration, drive it through the real code path, and fail loudly when an
extraction matches nothing (a gate that finds zero fields passes forever).

Nothing here claims a host token tool or a jury acceptance; it proves the two
halves of one contract agree.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / 'apps/workbench' / 'shell.ts'
WORKBENCH_TS = REPO / 'apps/workbench' / 'workbench.ts'
HTTP_SERVICE = REPO / 'src' / 'design_lab' / 'http_service.py'
sys.path.insert(0, str(REPO / 'src'))

from design_lab import design_layer  # noqa: E402
from design_lab.design_layer import DesignLayer, DesignLayerError  # noqa: E402
from design_lab.interop import dtcg  # noqa: E402
from design_lab.service import ProjectService  # noqa: E402


def _block(name: str) -> str:
    """The body of `export const <name> = [...] as const` in shell.ts."""
    text = SHELL.read_text(encoding='utf-8')
    match = re.search(rf"export const {name} = \[(.*?)\] as const", text, re.S)
    assert match, (f'{name} is no longer declared in shell.ts -- the page stopped '
                   f'declaring its half of the contract, which must read as a failure')
    return match.group(1)


def declared_readback_fields() -> list[str]:
    fields = re.findall(r"'([a-z0-9_]+)'", _block('TOKEN_DOCUMENT_FIELDS'))
    assert fields, 'TOKEN_DOCUMENT_FIELDS declared no field'
    return fields


def declared_write_fields() -> list[str]:
    fields = re.findall(r"'([a-z0-9_]+)'", _block('TOKEN_WRITE_FIELDS'))
    assert fields, 'TOKEN_WRITE_FIELDS declared no body key'
    return fields


def declared_sample() -> dict:
    """The document the editor offers for a first write, as the real object."""
    text = SHELL.read_text(encoding='utf-8')
    match = re.search(r"export const TOKEN_SAMPLE_DOCUMENT =\s*'([^']*)'", text)
    assert match, ('TOKEN_SAMPLE_DOCUMENT is no longer a single-quoted string literal in '
                   'shell.ts; re-read this gate instead of relaxing it')
    document = json.loads(match.group(1))
    assert isinstance(document, dict) and document, 'the sample must be a JSON object'
    return document


def editor_prefill_line() -> str:
    """The one line that decides what the textarea holds when the panel renders."""
    text = SHELL.read_text(encoding='utf-8')
    match = re.search(r"editor\.value = [^\n]*", text)
    assert match, 'the token editor no longer sets its own starting value'
    return match.group(0)


def write_the_pages_own_document() -> dict:
    """Run the page's document through the real write path; return the readback row."""
    parent = REPO / '.project-local' / 'task-runtime' / 'token-form-contract-tests'
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        root = Path(temporary)
        (root / 'AGENTS.md').write_text('# synthetic token form contract project', encoding='utf-8')
        env = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(root / '.project-local')})
        env.start()
        try:
            service = ProjectService(str(root))
            project_id = service.create_project('Token form contract')['id']
            layer = DesignLayer(service)
            written = layer.write_tokens(
                project_id, 'uiux-commercial-light', document=declared_sample(),
                expected_version=0, actor='workbench-user', actor_kind='human',
                idempotency_key='contract-1')['token_document']
            listed = layer.list_token_documents(project_id)['token_documents'][0]
            assert listed == written, 'the list readback drifted from the write readback'
            return written
        finally:
            env.stop()


class TokenFormContractTests(unittest.TestCase):
    def test_the_page_declares_exactly_the_fields_the_service_emits(self):
        declared = declared_readback_fields()
        emitted = sorted(write_the_pages_own_document())
        self.assertEqual(sorted(declared), emitted,
                         'the column prints fields the service does not send, or stops '
                         'printing fields it does')
        self.assertEqual(len(declared), len(set(declared)), 'duplicate field declared')

    def test_the_page_posts_exactly_the_body_keys_the_route_accepts(self):
        declared = declared_write_fields()
        self.assertEqual(sorted(declared), sorted(design_layer.TOKEN_WRITE_FIELDS),
                         'the route would refuse this form as INVALID_PROJECT_FIELDS')

    def test_the_sample_document_passes_the_real_dtcg_contract(self):
        document = declared_sample()
        report = dtcg.validate_document(document)   # raises on anything non-canonical
        self.assertGreaterEqual(report['token_count'], 1)
        self.assertEqual(report['schemaVersion'], dtcg.SCHEMA_VERSION)

    def test_the_service_persists_and_returns_the_pages_document_unchanged(self):
        """Not just the validator: the whole write path round-trips what the page offers."""
        record = write_the_pages_own_document()
        self.assertEqual(record['document'], declared_sample())
        self.assertEqual(record['token_count'],
                         dtcg.validate_document(declared_sample())['token_count'])
        self.assertEqual(record['dtcg_schema_version'], dtcg.SCHEMA_VERSION)
        self.assertEqual(record['version'], 1)
        self.assertEqual(record['actor_kind'], 'human',
                         'the page posts a human reviewer; the record must say so')

    def test_the_editor_starts_from_the_persisted_document_not_a_template(self):
        """A revision edits what the service really holds; the sample is only the
        first-write starting point."""
        line = editor_prefill_line()
        self.assertIn('live ? JSON.stringify(live.document, null, 2) : TOKEN_SAMPLE_DOCUMENT',
                      line, line)

    def test_the_refusal_reason_has_a_channel_to_the_page(self):
        """detail: is emitted by the route and forwarded by api() -- both ends, or the
        field-level reason dies in the transport and the reviewer gets a bare code."""
        http = HTTP_SERVICE.read_text(encoding='utf-8')
        self.assertIn("payload['detail'] = exc.detail[:10]", http,
                      'http_service must forward the refusal detail')
        transport = WORKBENCH_TS.read_text(encoding='utf-8')
        self.assertIn('failure.serviceEnvelope = value', transport,
                      'api() must carry the error envelope, not only its code')
        shell = SHELL.read_text(encoding='utf-8')
        self.assertIn('serviceEnvelope', shell,
                      'the token panel must read the envelope it is given')

    def test_a_stale_revision_is_recoverable_wording(self):
        shell = SHELL.read_text(encoding='utf-8')
        self.assertIn("errMsg(error) === 'STALE_REVISION'", shell,
                      'the page must recognise the recoverable conflict it can cause')
        self.assertIn('revisionHint(error)', shell)

    def test_the_page_does_not_advertise_publish_or_rollback(self):
        """G5 is still a gap: the column may not claim routes that do not exist."""
        body = SHELL.read_text(encoding='utf-8')
        panel = body[body.index('export function renderTokenDocumentPanel'):]
        panel = panel[:panel.index('// ---- 最近交付')]
        route_paths = re.findall(r"/design-system-tokens[a-z${}/._-]*", panel)
        self.assertTrue(route_paths, 'the panel no longer names its own route')
        for route in route_paths:
            self.assertNotIn('/publish', route)
            self.assertNotIn('/rollback', route)
        self.assertIn('发布与回滚尚无路由', panel)

    def test_unknown_design_system_still_refuses_the_pages_default(self):
        from design_lab.design_layer import catalog
        with self.assertRaises(DesignLayerError) as caught:
            parent = REPO / '.project-local' / 'task-runtime' / 'token-form-contract-tests'
            parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=parent) as temporary:
                root = Path(temporary)
                (root / 'AGENTS.md').write_text('# x', encoding='utf-8')
                env = patch.dict(os.environ,
                                 {'PROJECT_LOCAL_ROOT': str(root / '.project-local')})
                env.start()
                try:
                    service = ProjectService(str(root))
                    project_id = service.create_project('Shape')['id']
                    DesignLayer(service).write_tokens(
                        project_id, 'not-a-catalog-name', document=declared_sample(),
                        expected_version=0, actor='workbench-user', actor_kind='human',
                        idempotency_key='unknown-1')
                finally:
                    env.stop()
        self.assertEqual(caught.exception.code, 'UNKNOWN_DESIGN_SYSTEM')
        self.assertTrue(any(entry['name'] == 'uiux-commercial-light' for entry in catalog()),
                        'the catalog the page lists from is empty; these checks prove nothing')


if __name__ == '__main__':
    unittest.main()

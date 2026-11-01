# SPDX-License-Identifier: MIT
"""The automation-connector projection: what it may say, and what it must never imply.

owner 2026-10-28 lifted the freeze on the automation capability class, so this projection is
the first surface for it. Its whole job is to be unable to overstate: it reads two committed
records, answers NOT_PROBED for every connector, and cannot accidentally report a host as
reachable, a tool count as a capability, or an empty table as "no connectors exist".

Case 5 is the guard against the class of defect this repo keeps documenting -- a scan that
cannot fail. It runs the same predicate against a module that DOES spawn processes and
requires it to convict that module, so a green "no host launch" reading is not an empty
population.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab import automation_connectors as ac  # noqa: E402


def write_root(files: dict[str, str]) -> Path:
    """A scratch root under the project's own runtime dir.

    NOT tempfile.TemporaryDirectory(): this repo's CI runners set TMPDIR inside the
    workspace, so a tempdir does not mean "outside the repository" and a test that leans on
    that distinction has been red here before.
    """
    import hashlib
    root = (REPO / '.project-local' / 'task-runtime' / 'automation-connector-tests'
            / hashlib.sha256(json.dumps(sorted(files)).encode()).hexdigest()[:16])
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding='utf-8', newline='')
    return root


class ProjectionFollowsTheRegisteredRoster(unittest.TestCase):
    def setUp(self):
        self.view = ac.build()

    def test_the_roster_and_its_counts_come_from_the_same_rows(self):
        self.assertEqual(self.view['registry_state'], 'READ')
        self.assertEqual(self.view['pack_state'], 'READ')
        rows = self.view['connectors']
        counts = self.view['counts']
        self.assertEqual(counts['connectors'], len(rows))
        self.assertEqual(counts['handshaked_in_pack_evidence'],
                         sum(1 for row in rows if row['handshaked_in_pack_evidence']))
        self.assertEqual(counts['tools_listed_total_in_pack_evidence'],
                         sum(row['tools_listed_in_pack_evidence'] or 0 for row in rows))
        self.assertEqual(counts['connectors'], 11)
        self.assertEqual({row['id'] for row in rows},
                         {'sketchup', 'grasshopper', 'autocad', 'rhino', 'blender', '3dsmaxMCP',
                          'indesign', 'revit', 'photoshop', 'illustrator', 'windows'})

    def test_every_connector_is_unprobed_and_disabled_and_says_why(self):
        for row in self.view['connectors']:
            self.assertEqual(row['design_lab_state'], 'NOT_PROBED', row['id'])
            self.assertFalse(row['design_lab_enabled'], row['id'])
        self.assertEqual(self.view['counts']['probed_by_design_lab'], 0)
        self.assertEqual(self.view['counts']['enabled'], 0)
        self.assertEqual(self.view['counts']['native_tool_calls_executed'], 0)
        # The page must not be able to read a tool list as a capability count.
        self.assertIn('不把 543 条已列工具读成本项目已具备的能力数', self.view['claims_not_made'])

    def test_the_windows_desktop_ui_connector_is_named_as_owner_closed(self):
        windows = [row for row in self.view['connectors'] if row['id'] == 'windows']
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]['activation'], 'NOT_ACTIVATED_BY_OWNER')
        self.assertEqual(windows[0]['rights'], 'OUT_OF_SCOPE_THIS_ROUND')

    def test_the_same_named_join_names_adapters_it_actually_found(self):
        """A uniformly-false boolean would be a claim nobody checked; this one is computed."""
        joined = {row['id']: row['same_named_project_adapters'] for row in self.view['connectors']}
        self.assertIn('adapter-blender', joined['blender'])
        self.assertIn('adapter-photoshop-mcp', joined['photoshop'])
        self.assertIn('adapter-illustrator-mcp', joined['illustrator'])
        self.assertEqual(joined['revit'], [])
        self.assertEqual(joined['sketchup'], [])
        # The rows this pack itself registered must not count as independent evidence: if
        # adapter-delivery-* were included, all eleven connectors would report a join and the
        # field would be true by construction.
        for row_join in joined.values():
            self.assertFalse([a for a in row_join if a.startswith('adapter-delivery-')],
                             f'the join includes its own registration row: {joined}')
        # The join is a name match, not an identity finding, and says so where it is read.
        self.assertNotIn('同一上游实现', json.dumps(self.view, ensure_ascii=False))

    def test_the_registered_rows_are_declared_and_never_available(self):
        """Absorption lands in the project's own registry, at a status it can defend."""
        registry = json.loads((REPO / 'integrations/adapter-registry.json').read_text(
            encoding='utf-8'))
        delivery = [row for row in registry['adapters']
                    if str(row.get('adapter_id', '')).startswith('adapter-delivery-')]
        self.assertEqual(len(delivery), 11)
        for row in delivery:
            # `declared` and `missing` are both non-availability words in this registry; what must
            # never appear is a status that reads as usable. Blender specifically has to be
            # `missing`, because test_oda4_0206_adapters refuses any Blender row that claims more
            # than registration -- asserting `declared` here would have contradicted that guard.
            self.assertIn(row['status'], ('declared', 'missing'), row['adapter_id'])
            self.assertNotIn(row['status'], ('runtime', 'structural', 'available'),
                             f"{row['adapter_id']} claims a readiness its E1 record cannot carry")
            self.assertEqual(row['evidence']['level'], 'E1', row['adapter_id'])
            self.assertTrue([c for c in row['capabilities'] if not c['supported']],
                            f"{row['adapter_id']} presents an unsupported capability as there")
            self.assertIn('called no tool', row['evidence']['note'])
            # Only a bridge the pack actually handshook can be quoted as having listed tools;
            # grasshopper and windows never completed a handshake, so their notes must not
            # carry a listing claim.
            if 'the pack handshook this bridge' in row['evidence']['note']:
                self.assertIn('nativeToolCalled:false', row['evidence']['note'])
            else:
                self.assertIn('did not handshake', row['evidence']['note'])
        # Blender is a large tool: the registry gate refuses to let it read as available and
        # requires process isolation, so the row must satisfy both.
        blender = [row for row in delivery if row['adapter_id'] == 'adapter-delivery-blender'][0]
        self.assertEqual(blender['mode'], 'process-isolated')
        self.assertEqual(blender['status'], 'missing',
                         'the large-tools guard reads a `declared` Blender row as an availability '
                         'claim, so this row has to say the weaker word')
        self.assertTrue(blender['fallback'], 'a `missing` row must name its fallback')
        windows = [row for row in delivery if row['adapter_id'] == 'adapter-delivery-windows'][0]
        self.assertIn('NOT ACTIVATED', windows['evidence']['note'])


class AbsenceIsStatedNotInvented(unittest.TestCase):
    def test_a_missing_record_yields_a_named_state_not_an_empty_table(self):
        root = write_root({})
        view = ac.build(root)
        self.assertEqual(view['registry_state'], 'MISSING')
        self.assertEqual(view['pack_state'], 'MISSING')
        self.assertEqual(view['connectors'], [])
        self.assertEqual(view['counts']['connectors'], 0)
        # An empty table with no reason reads as "this project knows of no connectors".
        self.assertTrue(view['meaning'])
        self.assertTrue(view['unprobedMeans'])

    def test_an_unreadable_manifest_is_UNREADABLE_rather_than_MISSING_or_a_crash(self):
        root = write_root({str(ac.PACK_REL): '{ not json'})
        view = ac.build(root)
        self.assertEqual(view['pack_state'], 'UNREADABLE')
        self.assertEqual(view['connectors'], [])

    def test_dropping_a_row_moves_the_counts_with_it(self):
        """The denominators are derived, so a smaller population cannot keep the old total."""
        manifest = json.loads((REPO / ac.PACK_REL).read_text(encoding='utf-8'))
        manifest['connectors']['rows'] = manifest['connectors']['rows'][:3]
        root = write_root({
            str(ac.PACK_REL): json.dumps(manifest, ensure_ascii=False),
            str(ac.REGISTRY_REL): (REPO / ac.REGISTRY_REL).read_text(encoding='utf-8'),
        })
        view = ac.build(root)
        self.assertEqual(view['counts']['connectors'], 3)
        self.assertEqual(view['counts']['tools_listed_total_in_pack_evidence'],
                         sum(row['tools_listed_in_pack_evidence'] or 0
                             for row in view['connectors']))


class TheProjectionCannotReachAHost(unittest.TestCase):
    """No process, no socket, no HTTP: the module's own imports are the evidence."""

    FORBIDDEN = ('subprocess', 'socket', 'http.client', 'urllib.request', 'requests',
                 'asyncio.subprocess', 'os.system', 'ptyprocess')

    def findings(self, source: str) -> list[str]:
        hits = []
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped.startswith(('import ', 'from ')):
                continue
            for needle in self.FORBIDDEN:
                if needle in stripped.replace("'", '').replace('"', ''):
                    hits.append(f'{needle}: {stripped}')
        return hits

    def test_the_projection_module_imports_no_process_or_network_primitives(self):
        source = (REPO / 'src' / 'design_lab' / 'automation_connectors.py').read_text(
            encoding='utf-8')
        self.assertEqual([], self.findings(source),
                         'the read-only projection grew a way to reach a host or a port')

    def test_the_same_ruler_convicts_a_module_that_does_spawn(self):
        """Control: without this, the case above could pass on a scan that sees nothing.

        `src/design_lab/adapters/photoshop_com.py` really does drive the host through
        PowerShell, so a ruler that cannot convict it is not guarding the projection.
        """
        source = (REPO / 'src' / 'design_lab' / 'adapters' / 'photoshop_com.py').read_text(
            encoding='utf-8')
        hits = self.findings(source)
        self.assertTrue(hits,
                        'the control module no longer spawns anything, or the ruler has gone '
                        'blind -- either way the read-only case above proves nothing')
        self.assertIn('subprocess', ' '.join(hits))

    def test_a_planted_import_is_convicted(self):
        planted = ('import json\nfrom pathlib import Path\nimport subprocess\n'
                   'from http.client import HTTPConnection\n')
        hits = self.findings(planted)
        self.assertIn('subprocess', ' '.join(hits))
        self.assertIn('http.client', ' '.join(hits))


if __name__ == '__main__':
    unittest.main(verbosity=2)

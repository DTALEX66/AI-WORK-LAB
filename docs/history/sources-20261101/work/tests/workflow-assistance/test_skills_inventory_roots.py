import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('inventory', ROOT / 'scripts/ci/generate_skills_inventory.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryRootsTests(unittest.TestCase):
    def test_includes_core_and_canonical_project_source_once(self):
        runtime = ROOT / '.project-local/runs/tmp'
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as td:
            repo = Path(td)
            paths = ['integrations/executors/codex/skills/client',
                     'packages/client-neutral-core/skills/core',
                     'projections/agents/source/project',
                     '.agents/skills/project']
            for path in paths:
                folder = repo / path
                folder.mkdir(parents=True)
                (folder / 'SKILL.md').write_text('---\nname: fixture\n---\n', encoding='utf-8')
            skills, sources = module.discover_skills(repo)
            self.assertEqual(len(skills), 3)
            self.assertEqual({s['name'] for s in skills}, {'client', 'core', 'project'})
            self.assertFalse(any('.agents' in source for source in sources))

"""Negative controls for the Observer read-only boundary verifier.

The verifier exists to stop three regressions: a non-GET handler on the serving
surface, a write verb in the Observer's data layer, and an unguarded
authoritative write control in its UI. A verifier that only ever sees clean
input proves nothing, so each rule is exercised against a deliberately broken
copy of the tree in a temp directory.

Nothing here touches the real repository's tracked content: the fixture is a small synthetic
`apps/observer` tree, built under the project runtime root by ``project_temp.fixture_dir`` so a
failed release can never spill outside the boundary either
(``.project/governance/project-data-boundary.json``).
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "scripts" / "ci" / "verify_observer_readonly_boundary.py"
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import project_temp  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location("observer_readonly_verifier", SPEC)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V = _load()

GOOD_SIDECAR = '''
class Handler:
    def do_GET(self):
        self.send_json(200, {})

    def do_POST(self):
        self.send_json(405, {"status": "method_not_allowed"})

    def do_PUT(self):
        self.send_json(405, {"status": "method_not_allowed"})

    def do_PATCH(self):
        self.send_json(405, {"status": "method_not_allowed"})

    def do_DELETE(self):
        self.send_json(405, {"status": "method_not_allowed"})
'''

BAD_SIDECAR = '''
class Handler:
    def do_GET(self):
        self.send_json(200, {})

    def do_POST(self):
        self.apply_change(self.body())

    def do_PUT(self):
        self.send_json(405, {"status": "method_not_allowed"})

    def do_PATCH(self):
        self.send_json(405, {"status": "method_not_allowed"})

    def do_DELETE(self):
        self.send_json(405, {"status": "method_not_allowed"})
'''

GOOD_API = """
export async function fetchSnapshot(url: string) {
  return fetch(url, { method: 'GET', headers: { Accept: 'application/json' } })
}
"""

BAD_API = """
export async function approveTask(url: string) {
  return fetch(url, { method: 'POST', body: '{}' })
}
"""

GOOD_VIEW = """
export function View() {
  return (
    <button type="button" onClick={onPublish} disabled={publishDisabled}>保存并发布</button>
  )
}
"""

BAD_VIEW = """
export function View() {
  return (
    <button type="button" onClick={onPublish}>保存并发布</button>
  )
}
"""


class BoundaryNegativeControls(unittest.TestCase):
    def _tree(self, *, sidecar: str = GOOD_SIDECAR, files: dict[str, str] | None = None) -> Path:
        # The verifier resolves every rule relative to the root it is handed, so an in-boundary
        # fixture exercises exactly the same code path the system-temp root used to.
        tmp = project_temp.fixture_dir(prefix="nf24-tree-")
        (tmp / "services" / "orchestration").mkdir(parents=True)
        (tmp / "services" / "orchestration" / "sidecar.py").write_text(sidecar, encoding="utf-8")
        src = tmp / "apps" / "observer" / "frontend" / "src"
        src.mkdir(parents=True)
        (src / "api.ts").write_text(GOOD_API, encoding="utf-8")
        for rel, text in (files or {}).items():
            target = src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return tmp

    # --- R1 runtime ----------------------------------------------------
    def test_clean_tree_passes(self) -> None:
        self.assertEqual(V.verify(self._tree()), 0)

    def test_non_get_handler_that_writes_fails(self) -> None:
        self.assertEqual(V.verify(self._tree(sidecar=BAD_SIDECAR)), 1)

    def test_missing_non_get_handler_fails(self) -> None:
        bare = "class Handler:\n    def do_GET(self):\n        pass\n"
        self.assertEqual(V.verify(self._tree(sidecar=bare)), 1)

    def test_missing_get_handler_fails(self) -> None:
        no_get = GOOD_SIDECAR.replace("def do_GET(self):", "def do_HEAD(self):")
        self.assertEqual(V.verify(self._tree(sidecar=no_get)), 1)

    # --- R2 data layer -------------------------------------------------
    def test_post_in_data_layer_fails(self) -> None:
        tmp = self._tree()
        (tmp / "apps/observer/frontend/src/api.ts").write_text(BAD_API, encoding="utf-8")
        self.assertEqual(V.verify(tmp), 1)

    def test_write_verb_in_a_component_fails(self) -> None:
        self.assertEqual(V.verify(self._tree(files={"view.tsx": BAD_API})), 1)

    def test_write_verb_inside_a_comment_does_not_fail(self) -> None:
        commented = "// historically we used method: 'POST' here\n" + GOOD_API
        tmp = self._tree()
        (tmp / "apps/observer/frontend/src/api.ts").write_text(commented, encoding="utf-8")
        self.assertEqual(V.verify(tmp), 0)

    # --- R3 active write controls --------------------------------------
    def test_unguarded_write_button_fails(self) -> None:
        self.assertEqual(V.verify(self._tree(files={"view.tsx": BAD_VIEW})), 1)

    def test_disabled_write_button_passes(self) -> None:
        self.assertEqual(V.verify(self._tree(files={"view.tsx": GOOD_VIEW})), 0)

    def test_unguarded_approve_button_fails(self) -> None:
        view = 'export function V(){return <button type="button" onClick={approve}>批准</button>}'
        self.assertEqual(V.verify(self._tree(files={"view.tsx": view})), 1)

    def test_plain_read_only_text_is_not_a_control(self) -> None:
        view = 'export function V(){return <p>本视图只读：不提供批准 / 拒绝按钮</p>}'
        self.assertEqual(V.verify(self._tree(files={"view.tsx": view})), 0)

    def test_disabled_approve_button_passes(self) -> None:
        view = ('export function V(){return <button type="button" onClick={a} '
                'disabled={!ready}>批准</button>}')
        self.assertEqual(V.verify(self._tree(files={"view.tsx": view})), 0)

    # --- environment ---------------------------------------------------
    def test_missing_observer_tree_is_an_environment_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(V.verify(Path(tmp)), 2)


if __name__ == "__main__":
    unittest.main()

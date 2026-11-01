# SPDX-License-Identifier: MIT
"""Fixed local UI resources; never serve arbitrary paths or project assets."""
from hashlib import sha256
from importlib.resources import files
from pathlib import Path

ROUTES = {'/workbench': ('index.html', 'text/html'),
          '/workbench/main.js': ('build/main.js', 'text/javascript'),
          '/workbench/style.css': ('style.css', 'text/css')}
# Build Output Truth (D003): the Vite outDir is apps/workbench/build, committed to
# the repo (MiniGame committed-bundle pattern). Both the packaged wheel
# (design_lab/resources/workbench/build/main.js, via pyproject force-include) and the
# source checkout (apps/workbench/build/main.js) resolve through this single route.
#
# That resolution does NOT by itself guarantee the served bytes are the committed
# bytes: an installed copy wins whenever it exists, so a wheel built last week keeps
# serving its own bundle even when the checkout next to it has moved on. Probed on a
# real machine: installed build/main.js 72,051 B (Sep 27) vs committed 157,747 B
# (Oct 6) -- the earlier claim here that the served bundle "can never diverge" was
# wrong. served_bundle_sha256() makes the divergence observable, and
# design-lab/scripts/verify_workbench_packaging.py fails the wheel-install job when
# the installed bytes differ from the committed ones.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
       "img-src data:; connect-src 'self'; base-uri 'none'; form-action 'none'; "
       "frame-ancestors 'none'; object-src 'none'")


def resource(route):
    name, mime = ROUTES[route]
    packaged = files('design_lab').joinpath('resources', 'workbench', name)
    if packaged.is_file():
        return packaged.read_bytes(), mime
    # Source checkout only; never search the user-supplied project root.
    source = Path(__file__).resolve().parents[2] / 'apps' / 'workbench' / name
    return source.read_bytes(), mime


def bundle_origin():
    """Which copy this process serves: 'packaged' (installed wheel) or 'source'."""
    name = ROUTES['/workbench/main.js'][0]
    packaged = files('design_lab').joinpath('resources', 'workbench', name)
    return 'packaged' if packaged.is_file() else 'source'


def served_bundle_sha256():
    """Digest of the bundle this process actually serves (not of a source file)."""
    return sha256(resource('/workbench/main.js')[0]).hexdigest()

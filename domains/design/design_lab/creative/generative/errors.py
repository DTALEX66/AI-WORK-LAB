# SPDX-License-Identifier: MIT
"""Shared error type for the generative runtime contracts (Wave D).

Kept in its own module so submodules can raise it without importing the package
initialiser, which would be circular.
"""


class GenerativeError(RuntimeError):
    """Generative contract violation."""

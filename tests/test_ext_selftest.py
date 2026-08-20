"""Runs `ext/`'s own unittest suite, so one `pytest` covers the whole repo.

That suite is not collected directly (see pytest.ini): it lives inside the
`ext` package and uses relative imports, so it needs `python -m ext.selftest`
to load. It also installs its wrappers over the upstream app's module globals
for the duration of the run, which is exactly the kind of global mutation that
should not leak into other tests — a subprocess keeps it contained.

It remains the deck's own suite, runnable on its own in the deck venv via
`task xl:test`. This is a wrapper, not a replacement.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Any

from conftest import STREAMDECK


def test_the_extension_selftest_passes(app: Any) -> None:
    env = dict(os.environ, PYTHONPATH=str(STREAMDECK))
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ext.selftest"],
        cwd=STREAMDECK, env=env, capture_output=True, text=True,
        check=False, timeout=300,
    )
    assert result.returncode == 0, (
        f"`python -m ext.selftest` failed:\n{result.stdout[-2000:]}\n"
        f"{result.stderr[-4000:]}"
    )
    # unittest reports to stderr. Assert a plausible number of tests actually
    # ran, so a suite that silently stops collecting doesn't read as a pass.
    ran = re.search(r"^Ran (\d+) tests?", result.stderr, re.M)
    assert ran, result.stderr[-2000:]
    assert int(ran.group(1)) >= 30, f"only {ran.group(1)} tests ran"

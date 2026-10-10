"""The kitchen timer's C++ helpers, compiled and run on the host.

`kitchen-timer/kitchen_timer_helpers.h` turns Home Assistant's timer attributes
into numbers the display can count down from. It is the one piece of the
firmware with real logic and no hardware dependency, and it sits on a seam: a
wrong timezone sign or a dropped fractional second doesn't fail anywhere, the
timer just shows the wrong time or rings early. So it gets compiled with the
host compiler and its assertions run here, in milliseconds, instead of being
found on the kitchen wall.

Skips when no C++ compiler is installed; CI's Ubuntu image has g++.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import KITCHEN_TIMER

SOURCE = KITCHEN_TIMER / "tests" / "test_helpers.cpp"


def test_the_helper_tests_exist() -> None:
    assert SOURCE.exists(), f"missing {SOURCE}"


def test_helpers_compile_cleanly_and_pass(tmp_path: Path) -> None:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("no C++ compiler on this machine")
    binary = tmp_path / "test_helpers"
    # -Werror: the firmware build is stricter than a default host build, so a
    # warning here is worth knowing about before it is a flash-time surprise.
    # -UNDEBUG: the tests are plain assert(); never let a define silence them.
    build = subprocess.run(  # noqa: S603
        [compiler, "-std=gnu++20", "-Wall", "-Wextra", "-Werror", "-UNDEBUG",
         str(SOURCE), "-o", str(binary)],
        capture_output=True, text=True, check=False,
    )
    assert build.returncode == 0, f"compile failed:\n{build.stderr}"
    run = subprocess.run(  # noqa: S603
        [str(binary)], capture_output=True, text=True, check=False, timeout=60,
    )
    assert run.returncode == 0, f"helper tests failed:\n{run.stdout}{run.stderr}"

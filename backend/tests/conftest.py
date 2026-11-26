from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "engine", ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aiwish.data_gen import build_all_scenarios  # noqa: E402


@pytest.fixture(scope="session")
def scenarios():
    return build_all_scenarios()


@pytest.fixture(scope="session")
def solved_f(scenarios):
    from aiwish.runner import run_scenario
    return run_scenario(scenarios["F"], time_limit_seconds=20)


@pytest.fixture(scope="session")
def solved_a(scenarios):
    from aiwish.runner import run_scenario
    return run_scenario(scenarios["A"], time_limit_seconds=10)

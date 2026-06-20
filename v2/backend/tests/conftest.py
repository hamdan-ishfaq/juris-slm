import os
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent / "src"
V2_ROOT = TESTS_DIR.parents[1]
collect_ignore = ["test_e2e_comprehensive.py"]
for p in (str(TESTS_DIR), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Load v2/.env for integration tests (DB URL, API keys)
_env_file = V2_ROOT / ".env"
if _env_file.is_file():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val

from api_helpers import api_reachable, clear_rate_limits


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires running API stack")
    config.addinivalue_line("markers", "unit: fast isolated unit tests")


@pytest.fixture(scope="session")
def api_up():
    if not api_reachable():
        pytest.skip("API not reachable at JURIS_API_BASE (default http://localhost:8002)")
    return True


@pytest.fixture(autouse=True)
def _reset_rate_limits_for_integration(request):
    if request.node.get_closest_marker("integration"):
        clear_rate_limits()
    yield
    if request.node.get_closest_marker("integration"):
        import asyncio

        from db import engine

        asyncio.run(engine.dispose())

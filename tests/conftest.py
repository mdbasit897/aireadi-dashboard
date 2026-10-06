"""
Test fixtures. Every test runs against a small synthetic dataset generated
by scripts/make_synthetic_dataset.py — no AI-READI data is needed or used.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
N_SYNTHETIC = 160


def clear_service_caches() -> None:
    for name, mod in list(sys.modules.items()):
        if name.startswith("services") or name == "config":
            for attr in vars(mod).values():
                if callable(attr) and hasattr(attr, "cache_clear"):
                    attr.cache_clear()


@pytest.fixture(scope="session")
def synthetic_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("synthetic_dataset")
    results = tmp_path_factory.mktemp("results")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "make_synthetic_dataset.py"),
         "--out", str(root), "--n", str(N_SYNTHETIC), "--seed", "1"],
        check=True, capture_output=True,
    )
    os.environ["DATASET_ROOT"] = str(root)
    os.environ["RESULTS_DIR"] = str(results)
    clear_service_caches()
    yield {"root": root, "results": results}
    clear_service_caches()


@pytest.fixture(scope="session")
def client(synthetic_env):
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


@pytest.fixture
def run_script(synthetic_env):
    """Run a pipeline script as a subprocess against the synthetic dataset."""
    def _run(name: str, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "DATASET_ROOT": str(synthetic_env["root"]),
               "RESULTS_DIR": str(synthetic_env["results"])}
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / name), *args],
            env=env, capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert proc.returncode == 0, f"{name} failed:\n{proc.stdout}\n{proc.stderr}"
        return proc
    return _run

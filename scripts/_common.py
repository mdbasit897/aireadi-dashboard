"""
Shared helpers for the offline evidence pipeline in scripts/.

Every script writes into the results directory (settings.results_dir,
default <repo>/results) and stamps each JSON output with provenance:
generation time, git commit, dataset root and whether the dataset is the
synthetic test fixture. Per-participant outputs stay in results/ and are
git-ignored: they are derived from DUA-protected data.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from config import get_settings  # noqa: E402

TOOL_VERSION = "1.2.0"


def results_dir() -> Path:
    path = Path(get_settings().results_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def dataset_is_synthetic() -> bool:
    desc = Path(get_settings().dataset_root) / "dataset_description.json"
    try:
        return bool(json.loads(desc.read_text()).get("synthetic", False))
    except (OSError, json.JSONDecodeError):
        return False


def git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{out}{'-dirty' if dirty else ''}"
    except (OSError, subprocess.CalledProcessError):
        return None


def provenance(script: str, **params: Any) -> dict[str, Any]:
    return {
        "script":        script,
        "tool_version":  TOOL_VERSION,
        "generated_at":  datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit":    git_commit(),
        "dataset_root":  get_settings().dataset_root,
        "synthetic":     dataset_is_synthetic(),
        "params":        params,
    }


def _json_safe(obj: Any) -> Any:
    """NaN/inf → None and numpy scalars → Python, so the output is strict JSON."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            obj = obj.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def write_json(name: str, payload: dict[str, Any]) -> Path:
    path = results_dir() / name
    path.write_text(json.dumps(_json_safe(payload), indent=2, default=str, allow_nan=False))
    return path


def read_json(name: str) -> dict[str, Any] | None:
    path = results_dir() / name
    return json.loads(path.read_text()) if path.exists() else None


def load_readiness_table():
    import pandas as pd

    path = results_dir() / "participant_readiness.csv"
    if not path.exists():
        sys.exit(f"{path} not found. Run first:  python scripts/build_readiness_table.py")
    return pd.read_csv(path, dtype={"person_id": str})


def banner(title: str) -> None:
    print(f"\n{title}\n{'=' * len(title)}")
    print(f"DATASET_ROOT: {get_settings().dataset_root}")
    print(f"RESULTS_DIR:  {results_dir()}")
    if dataset_is_synthetic():
        print("NOTE: synthetic test dataset — numbers are NOT AI-READI results.")

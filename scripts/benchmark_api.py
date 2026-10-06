#!/usr/bin/env python3
"""
benchmark_api.py — step 5 of the evidence pipeline (Reviewer 3, comment 1;
Reviewer 4). Replaces the author-estimated task times with measured ones.

Measures, on the machine it runs on:
  * each readiness-workflow step through the dashboard REST API, cold
    (all in-process caches cleared before the call) and warm (repeat call);
  * the hand-written notebook-equivalent baseline
    (scripts/manual_readiness_baseline.py): wall-clock and analysis lines of code.

By default the API is exercised in-process with FastAPI's TestClient, so
"cold" is reproducible without restarting a server. Use --url to time a
running deployment over HTTP instead (cold = first request after start).
The OS page cache is not dropped; the first repeat is therefore the only
truly disk-cold run and is reported separately.

Output
  results/benchmark.json

Usage
  python scripts/benchmark_api.py [--repeats 5] [--participant 1023] [--url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import platform
import statistics
import sys
import time
from pathlib import Path

from _common import REPO_ROOT, banner, provenance, read_json, write_json

STEPS = [
    ("1 cohort scoping",           "/api/cohort/summary"),
    ("2 modality intersection",    "/api/eda/comissingness?study_group=insulin_dependent"),
    ("3 temporal check (1 part.)", "/api/eda/temporal-overlap/{pid}"),
    ("3b cohort temporal offsets", "/api/eda/temporal-offsets"),
    ("4 signal quality (live sample)", "/api/eda/signal-quality?source=sample"),
    ("4b signal quality (full cohort)", "/api/eda/signal-quality?source=precomputed"),
    ("5 label validation (HbA1c)", "/api/eda/labs/cohort"),
]


def clear_caches() -> None:
    """Clear every functools cache in the backend services (not get_settings)."""
    for name, mod in list(sys.modules.items()):
        if not name.startswith("services"):
            continue
        for attr in vars(mod).values():
            if callable(attr) and hasattr(attr, "cache_clear"):
                attr.cache_clear()


def hardware() -> dict:
    mem_gib = None
    with contextlib.suppress(OSError, ValueError, IndexError):
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                mem_gib = round(int(line.split()[1]) / 1024 / 1024, 1)
    return {"platform": platform.platform(), "python": platform.python_version(),
            "cpu_count": os.cpu_count(), "mem_gib": mem_gib, "processor": platform.processor()}


def stats(xs: list[float]) -> dict:
    return {"n": len(xs), "mean_s": round(statistics.mean(xs), 4) if xs else None,
            "sd_s": round(statistics.stdev(xs), 4) if len(xs) > 1 else None,
            "min_s": round(min(xs), 4) if xs else None, "max_s": round(max(xs), 4) if xs else None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--participant", default=None, help="participant for step 3 (default: first with ECG+CGM)")
    ap.add_argument("--url", default=None, help="time a running server over HTTP instead of in-process")
    ap.add_argument("--skip-manual", action="store_true")
    args = ap.parse_args()

    banner("Runtime benchmark")
    from services.cohort_service import load_participants

    parts = load_participants()
    pid = args.participant or str(
        parts[(parts["cardiac_ecg"] == True) & (parts["wearable_blood_glucose"] == True)]  # noqa: E712
        .iloc[0]["person_id"])

    if args.url:
        import httpx
        client = httpx.Client(base_url=args.url, timeout=600)
        mode = f"http {args.url}"
    else:
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        mode = "in-process TestClient"

    steps_out = {}
    for label, path in STEPS:
        url = path.format(pid=pid)
        cold, warm, status = [], [], None
        for _ in range(args.repeats):
            if not args.url:
                clear_caches()
            t0 = time.perf_counter()
            r = client.get(url)
            cold.append(time.perf_counter() - t0)
            status = r.status_code
            t0 = time.perf_counter()
            client.get(url)
            warm.append(time.perf_counter() - t0)
        if status == 404:
            steps_out[label] = {"endpoint": url, "status": 404, "note": "precomputed result not present"}
            print(f"  {label:<34} skipped (404: run the pipeline first)")
            continue
        steps_out[label] = {"endpoint": url, "status": status, "first_call_s": round(cold[0], 4),
                            "cold": stats(cold), "warm": stats(warm)}
        print(f"  {label:<34} cold {statistics.mean(cold):7.3f} s   warm {statistics.mean(warm):7.3f} s")

    manual = None
    if not args.skip_manual:
        from config import get_settings
        os.environ["DATASET_ROOT"] = get_settings().dataset_root
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import manual_readiness_baseline as mb
        mb.DATASET_ROOT = get_settings().dataset_root
        runs, output = [], ""
        for _ in range(args.repeats):
            buf = io.StringIO()
            t0 = time.perf_counter()
            try:
                with contextlib.redirect_stdout(buf):
                    mb.run()
            except Exception as exc:  # noqa: BLE001 — report, keep the API timings
                print(f"  manual baseline failed: {exc}")
                break
            runs.append(time.perf_counter() - t0)
            output = buf.getvalue()
    if not args.skip_manual and runs:
        manual = {"script": "scripts/manual_readiness_baseline.py", "analysis_loc": mb._count_analysis_loc(),
                  "what_it_computes": "triple ECG+CGM+clinical file overlap and same-day CGM co-registration "
                                      "for the insulin-dependent group, from raw files",
                  "wall_clock": stats(runs), "first_run_s": round(runs[0], 4), "last_output": output.strip()}
        print(f"  {'manual baseline (raw files)':<34} mean {statistics.mean(runs):7.3f} s   "
              f"LOC {manual['analysis_loc']}")

    pipeline = read_json("readiness_table_summary.json")
    payload = {
        "mode": mode, "participant_for_step_3": pid, "repeats": args.repeats,
        "steps": steps_out, "manual_baseline": manual,
        "offline_pipeline_cost_s": (pipeline or {}).get("elapsed_seconds"),
        "hardware": hardware(),
        "notes": [
            "cold = all in-process caches cleared before the call (OS page cache not dropped)",
            "steps 3b and 4b serve results precomputed by the offline pipeline; its one-off cost "
            "is offline_pipeline_cost_s (scripts/build_readiness_table.py)",
        ],
        "_meta": provenance("benchmark_api.py", repeats=args.repeats, url=args.url, participant=pid),
    }
    write_json("benchmark.json", payload)
    print("\nWrote results/benchmark.json")


if __name__ == "__main__":
    main()

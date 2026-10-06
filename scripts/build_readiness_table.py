#!/usr/bin/env python3
"""
build_readiness_table.py — step 1 of the evidence pipeline.

One pass over EVERY participant in participants.tsv (no sampling). For each
participant it reads the ECG header, the CGM file and the OMOP visit date
through the same functions the dashboard API uses
(services.eda_service.extract_participant_readiness), and writes one row to

    results/participant_readiness.csv     (per participant — git-ignored)
    results/readiness_table_summary.json  (aggregate counts and run time)

All later steps (ecg_date_audit.py, full_cohort_quality.py,
gating_experiment.py) read this table instead of re-scanning the dataset.

Usage:
    python scripts/build_readiness_table.py [--workers 8] [--limit N]
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor

from _common import banner, provenance, results_dir, write_json


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8, help="parallel file readers (I/O bound)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N participants (debugging)")
    args = ap.parse_args()

    import pandas as pd
    from services.cohort_service import load_participants
    from services.eda_service import earliest_visit_dates, extract_participant_readiness

    banner("Build participant readiness table")
    participants = load_participants()
    if args.limit:
        participants = participants.head(args.limit)
    earliest_visit_dates()  # warm the cache before threads start

    t0 = time.perf_counter()
    rows_in = [r for _, r in participants.iterrows()]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda r: extract_participant_readiness(str(r["person_id"]), r), rows_in))
    elapsed = time.perf_counter() - t0

    df = pd.DataFrame.from_records(records)
    out_csv = results_dir() / "participant_readiness.csv"
    df.to_csv(out_csv, index=False)

    summary = {
        "n_participants":       len(df),
        "n_flag_ecg":           int(df["flag_ecg"].sum()),
        "n_has_ecg_file":       int(df["has_ecg_file"].sum()),
        "n_ecg_header_ok":      int(df["ecg_header_ok"].sum()),
        "n_flag_cgm":           int(df["flag_cgm"].sum()),
        "n_has_cgm_file":       int(df["has_cgm_file"].sum()),
        "n_cgm_parsed":         int(df["cgm_start"].notna().sum()) if "cgm_start" in df else 0,
        "n_has_clinical":       int(df["has_clinical"].sum()),
        "n_with_visit_date":    int(df["visit_date"].notna().sum()),
        "flag_without_file": {
            "ecg": int((df["flag_ecg"] & ~df["has_ecg_file"]).sum()),
            "cgm": int((df["flag_cgm"] & ~df["has_cgm_file"]).sum()),
        },
        "file_without_flag": {
            "ecg": int((~df["flag_ecg"] & df["has_ecg_file"]).sum()),
            "cgm": int((~df["flag_cgm"] & df["has_cgm_file"]).sum()),
        },
        "elapsed_seconds":      round(elapsed, 1),
        "_meta":                provenance("build_readiness_table.py", workers=args.workers, limit=args.limit),
    }
    write_json("readiness_table_summary.json", summary)

    print(f"\nParticipants scanned ......... {len(df)}")
    print(f"ECG files / headers readable . {summary['n_has_ecg_file']} / {summary['n_ecg_header_ok']}")
    print(f"CGM files / parsed ........... {summary['n_has_cgm_file']} / {summary['n_cgm_parsed']}")
    print(f"Flag TRUE but file missing ... ECG {summary['flag_without_file']['ecg']}, "
          f"CGM {summary['flag_without_file']['cgm']}")
    print(f"Elapsed ...................... {elapsed:.1f} s")
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()

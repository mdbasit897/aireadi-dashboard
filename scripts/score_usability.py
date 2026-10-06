#!/usr/bin/env python3
"""
score_usability.py — scores the formative usability study
(docs/usability/usability_study_kit.md) from the filled data sheet.

Input   a CSV in the format of docs/usability/usability_results_template.csv
        (one row per participant; outcome = S success, A assisted, F fail;
        SUS items 1–5; U1/U2 1–5). Keep it outside git: it is study data.
Output  results/usability.json  (per-task time and success, SUS, U1/U2)

SUS scoring (Brooke, 1996): odd items contribute (response − 1), even items
(5 − response); the sum × 2.5 gives 0–100. 68 is the commonly cited average.

Usage
  python scripts/score_usability.py path/to/usability_results.csv
"""

from __future__ import annotations

import argparse
import statistics

from _common import provenance, write_json

TASKS = {
    1: "Cohort scoping",
    2: "Modality intersection",
    3: "Temporal co-registration",
    4: "Signal-quality gating",
    5: "Label validation",
}


def sus_score(row) -> float | None:
    try:
        items = [int(row[f"sus{i}"]) for i in range(1, 11)]
    except (KeyError, ValueError, TypeError):
        return None
    if any(not 1 <= v <= 5 for v in items):
        return None
    total = sum((v - 1) if i % 2 == 0 else (5 - v) for i, v in enumerate(items))
    return total * 2.5


def mean_sd(xs):
    xs = [x for x in xs if x is not None]
    return {"n": len(xs), "mean": round(statistics.mean(xs), 1) if xs else None,
            "sd": round(statistics.stdev(xs), 1) if len(xs) > 1 else None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    args = ap.parse_args()

    import pandas as pd
    from services.readiness_service import proportion

    df = pd.read_csv(args.csv, dtype=str).fillna("")
    n = len(df)
    tasks = {}
    for t, name in TASKS.items():
        outcome = df[f"t{t}_outcome"].str.strip().str.upper().str[:1]
        times = pd.to_numeric(df[f"t{t}_time_s"], errors="coerce")
        tasks[f"t{t}"] = {
            "task": name,
            "time_s": mean_sd(times[outcome == "S"].tolist()),          # unaided successes only
            "time_s_all": mean_sd(times.dropna().tolist()),
            "success_unaided": proportion(int((outcome == "S").sum()), n),
            "success_incl_assisted": proportion(int(outcome.isin(["S", "A"]).sum()), n),
        }
    sus = [sus_score(r) for _, r in df.iterrows()]
    to_num = lambda c: pd.to_numeric(df[c], errors="coerce").dropna().tolist()  # noqa: E731
    out = {
        "n_participants": n,
        "background_counts": df["background"].str.strip().str.lower().value_counts().to_dict(),
        "tasks": tasks,
        "sus": mean_sd(sus),
        "sus_above_68": proportion(sum(1 for s in sus if s is not None and s >= 68), sum(1 for s in sus if s is not None)),
        "u1_time_saving": mean_sd(to_num("u1_time_saving")),
        "u2_trust": mean_sd(to_num("u2_trust")),
        "_meta": provenance("score_usability.py", csv=args.csv),
    }
    write_json("usability.json", out)
    print(f"n = {n}; SUS {out['sus']['mean']} ± {out['sus']['sd']}")
    for k, t in tasks.items():
        print(f"  {t['task']:<26} {t['time_s']['mean']} ± {t['time_s']['sd']} s   "
              f"success {t['success_unaided']['pct']}%")
    print("Wrote results/usability.json")


if __name__ == "__main__":
    main()

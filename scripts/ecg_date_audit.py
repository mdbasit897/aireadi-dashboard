#!/usr/bin/env python3
"""
ecg_date_audit.py — step 2 of the evidence pipeline (Reviewer 3, comment 3).

"A 100% timestamp extraction rate does not necessarily confirm that all
recovered dates are correct." This script separates three questions:

  A. Extraction  — can a date be parsed from every header?       (coverage)
  B. Parsing     — is the parsed date the date written in the     (manual check
                   header?                                         of a sample)
  C. Meaning     — does `validation_date` behave like the          (offsets, date
                   acquisition date, or like a processing date?    clustering,
                                                                   field inventory)

Outputs
  results/ecg_date_audit.json                 aggregate audit (safe to report)
  results/ecg_manual_verification_sample.csv  stratified sample for two
                                              reviewers to check (git-ignored)

Usage
  python scripts/ecg_date_audit.py [--per-site 20] [--tau 7] [--seed 7]
  # after two people fill in the reviewer columns of the CSV:
  python scripts/ecg_date_audit.py --score results/ecg_manual_verification_sample.csv
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from _common import banner, load_readiness_table, provenance, read_json, results_dir, write_json

DATE_LIKE_VALUE = re.compile(r"^(\d{8}|\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?)$")
DATE_LIKE_KEY = re.compile(r"date|time", re.IGNORECASE)
SAFE_TO_LIST_MAX_DISTINCT = 6   # list values only for low-cardinality settings fields


def _raw_comment_lines(record_path: str) -> list[str]:
    with open(record_path + ".hea", errors="ignore") as f:
        return [ln.rstrip("\n") for ln in f if ln.startswith("#")]


def field_inventory(person_ids: list[str], workers: int) -> dict:
    """Every comment key across all headers: frequency, cardinality, date-likeness."""
    from services.eda_service import read_ecg_header
    from services.readiness_service import comments_to_dict

    def one(pid: str):
        h = read_ecg_header(pid)
        return comments_to_dict(h["comments"]) if h["ok"] else None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        dicts = [d for d in pool.map(one, person_ids) if d is not None]

    counts: Counter = Counter()
    values: dict[str, set] = defaultdict(set)
    for d in dicts:
        for k, v in d.items():
            counts[k] += 1
            values[k].add(v)

    fields = []
    for key, n in counts.most_common():
        vals = values[key]
        date_like = bool(DATE_LIKE_KEY.search(key)) or (
            sum(1 for v in vals if DATE_LIKE_VALUE.match(v)) >= 0.8 * len(vals)
        )
        entry = {"key": key, "n_headers": n, "n_distinct_values": len(vals), "date_like": date_like}
        if date_like:
            parsed = sorted(v for v in vals if DATE_LIKE_VALUE.match(v))
            entry["min_value"], entry["max_value"] = (parsed[0], parsed[-1]) if parsed else (None, None)
        elif len(vals) <= SAFE_TO_LIST_MAX_DISTINCT:
            entry["values"] = sorted(vals)
        fields.append(entry)
    return {"n_headers_read": len(dicts), "fields": fields}


def make_sample(df, per_site: int, seed: int, tau: int):
    import pandas as pd
    from services.eda_service import read_ecg_header

    pool = df[df["ecg_header_ok"] == True]  # noqa: E712
    parts = []
    for site, g in pool.groupby("clinical_site"):
        parts.append(g.sample(n=min(per_site, len(g)), random_state=seed))
    sample = pd.concat(parts) if parts else pool.head(0)

    rows = []
    for _, r in sample.iterrows():
        h = read_ecg_header(r["person_id"])
        raw = _raw_comment_lines(h["record_path"]) if h["ok"] else []
        vd_lines = [ln for ln in raw if "validation_date" in ln]
        other_dates = [ln for ln in raw if DATE_LIKE_KEY.search(ln.split(":")[0]) and "validation_date" not in ln]
        rows.append({
            "person_id":              r["person_id"],
            "clinical_site":          r["clinical_site"],
            "hea_file":               h.get("record_path", "") + ".hea",
            "raw_validation_date_line": " | ".join(vd_lines) or "(absent)",
            "other_date_like_lines":  " | ".join(other_dates),
            "parsed_ecg_date":        r.get("ecg_date"),
            "omop_visit_date":        r.get("visit_date"),
            "ecg_minus_visit_days":   r.get("ecg_offset_days"),
            "within_tau":             (abs(r["ecg_offset_days"]) <= tau) if pd.notna(r.get("ecg_offset_days")) else None,
            "reviewer_1_parse_correct": "",
            "reviewer_1_notes":       "",
            "reviewer_2_parse_correct": "",
            "reviewer_2_notes":       "",
        })
    return pd.DataFrame(rows)


def score(csv_path: str) -> None:
    """Agreement of each reviewer with the parser, and between reviewers (Cohen's kappa)."""
    import pandas as pd

    df = pd.read_csv(csv_path, dtype=str).fillna("")
    norm = lambda s: s.strip().upper()[:1]  # noqa: E731  Y / N
    r1 = df["reviewer_1_parse_correct"].map(norm)
    r2 = df["reviewer_2_parse_correct"].map(norm)
    done = (r1.isin(["Y", "N"])) & (r2.isin(["Y", "N"]))
    if not done.any():
        raise SystemExit("No rows with both reviewer columns filled (Y/N).")
    r1, r2 = r1[done], r2[done]
    n = int(done.sum())
    po = float((r1 == r2).mean())
    p_y1, p_y2 = float((r1 == "Y").mean()), float((r2 == "Y").mean())
    pe = p_y1 * p_y2 + (1 - p_y1) * (1 - p_y2)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0

    from services.readiness_service import proportion

    audit = read_json("ecg_date_audit.json") or {}
    audit["manual_verification"] = {
        "n_scored": n,
        "reviewer_1_parser_correct": proportion(int((r1 == "Y").sum()), n),
        "reviewer_2_parser_correct": proportion(int((r2 == "Y").sum()), n),
        "both_correct":              proportion(int(((r1 == "Y") & (r2 == "Y")).sum()), n),
        "inter_rater_agreement":     round(po, 3),
        "cohens_kappa":              round(kappa, 3),
        "by_site": {
            site: proportion(int(((r1 == "Y") & (r2 == "Y"))[g.index].sum()), len(g))
            for site, g in df[done].groupby("clinical_site")
        },
        "_meta": provenance("ecg_date_audit.py --score", csv=csv_path),
    }
    write_json("ecg_date_audit.json", audit)
    mv = audit["manual_verification"]
    print(f"Scored {n} records: parser correct (both reviewers) {mv['both_correct']['pct']}% "
          f"[{mv['both_correct']['ci95'][0]}, {mv['both_correct']['ci95'][1]}], kappa {mv['cohens_kappa']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-site", type=int, default=20, help="manual-verification records per site")
    ap.add_argument("--tau", type=int, default=7, help="co-registration tolerance in days")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--score", metavar="CSV", help="score a filled manual-verification CSV and exit")
    args = ap.parse_args()

    if args.score:
        score(args.score)
        return

    import pandas as pd
    from services.readiness_service import bin_offsets, interpret_validation_date, proportion

    banner("ECG validation_date audit")
    df = load_readiness_table()

    # A. Extraction coverage and failure modes
    flagged = df[df["flag_ecg"] == True]  # noqa: E712
    files = df[df["has_ecg_file"] == True]  # noqa: E712
    readable = df[df["ecg_header_ok"] == True]  # noqa: E712
    parsed = readable[readable["ecg_date"].notna()]
    failures = df.loc[df["has_ecg_file"] | df["flag_ecg"], "ecg_date_failure"].fillna("ok").value_counts().to_dict()
    extraction = {
        "n_flagged_ecg":          len(flagged),
        "n_hea_found":            len(files),
        "n_header_readable":      len(readable),
        "date_extracted":         proportion(len(parsed), len(readable)),
        "failure_modes":          {k: int(v) for k, v in failures.items() if k != "ok"},
        "n_participants_multiple_records": int((df["ecg_n_records"].fillna(0) > 1).sum()),
        "base_date_populated":    proportion(int(readable["ecg_base_date_set"].fillna(False).astype(bool).sum()),
                                             len(readable)),
        "parsing_rules": [
            "Split each '#' comment line at the first ':' into key and value; strip whitespace.",
            "Take the value of key 'validation_date'.",
            "Accept only exactly 8 digits forming a valid calendar date (YYYYMMDD).",
            "Otherwise record the failure as missing / malformed; unreadable or absent headers "
            "are header_read_error / no_hea_file.",
        ],
    }

    # C1. Date clustering
    dates = parsed["ecg_date"]
    vc = dates.value_counts()
    date_distribution = {
        "n_dates": int(len(dates)),
        "n_distinct": int(vc.size),
        "min": dates.min() if len(dates) else None,
        "max": dates.max() if len(dates) else None,
        "top_dates": [{"date": d, "n": int(k), "share_pct": round(k / len(dates) * 100, 1)}
                      for d, k in vc.head(10).items()],
        "share_top_1_pct": round(vc.iloc[0] / len(dates) * 100, 1) if len(dates) else None,
        "share_top_10_pct": round(vc.head(10).sum() / len(dates) * 100, 1) if len(dates) else None,
        "by_month": {m: int(k) for m, k in dates.str[:7].value_counts().sort_index().items()},
    }

    # C2. Plausibility rules
    visits = pd.to_datetime(df["visit_date"], errors="coerce")
    window_lo = visits.min() - pd.Timedelta(days=30)
    window_hi = visits.max() + pd.Timedelta(days=730)
    ed = pd.to_datetime(parsed["ecg_date"], errors="coerce")
    plausibility = {
        "study_window": [str(window_lo.date()) if pd.notna(window_lo) else None,
                         str(window_hi.date()) if pd.notna(window_hi) else None],
        "outside_study_window": proportion(int(((ed < window_lo) | (ed > window_hi)).sum()), len(ed)),
        "before_visit": proportion(int((parsed["ecg_offset_days"] < 0).sum()),
                                   int(parsed["ecg_offset_days"].notna().sum())),
        "visit_tsv_vs_omop_mismatch": proportion(
            int((df["visit_tsv_offset_days"].fillna(0) != 0).sum()),
            int(df["visit_tsv_offset_days"].notna().sum())),
    }

    # C3. Offset distributions, overall / by site / by group
    def offsets_for(column: str) -> dict:
        out = {"overall": bin_offsets(df[column].tolist())}
        out["by_site"] = {s: bin_offsets(g[column].tolist()) for s, g in df.groupby("clinical_site")}
        out["by_group"] = {s: bin_offsets(g[column].tolist()) for s, g in df.groupby("study_group")}
        return out

    offsets = {
        "anchor": "earliest OMOP visit_start_date (calendar date)",
        "ecg_minus_visit": offsets_for("ecg_offset_days"),
        "cgm_minus_visit": offsets_for("cgm_offset_days"),
        "ecg_minus_cgm":   offsets_for("ecg_cgm_offset_days"),
    }
    both = df["ecg_offset_days"].notna() & df["cgm_offset_days"].notna()
    co_reg = both & (df["ecg_offset_days"].abs() <= args.tau) & (df["cgm_offset_days"].abs() <= args.tau)
    offsets["ecg_and_cgm_within_tau_of_visit"] = proportion(int(co_reg.sum()), int(both.sum()))
    offsets["tau_days"] = args.tau

    interpretation = interpret_validation_date(
        offsets["ecg_minus_visit"]["overall"], date_distribution["n_distinct"],
        date_distribution["n_dates"], args.tau)

    firmware_by_site = {
        s: {k: int(v) for k, v in g["ecg_firmware"].fillna("(missing)").value_counts().items()}
        for s, g in readable.groupby("clinical_site")
    } if "ecg_firmware" in readable else {}

    inventory = field_inventory(readable["person_id"].tolist(), args.workers)

    audit = read_json("ecg_date_audit.json") or {}
    audit.update({
        "extraction":                    extraction,
        "date_distribution":             date_distribution,
        "plausibility":                  plausibility,
        "offsets":                       offsets,
        "validation_date_interpretation": interpretation,
        "firmware_by_site":              firmware_by_site,
        "field_inventory":               inventory,
        "_meta":                         provenance("ecg_date_audit.py", per_site=args.per_site,
                                                    tau=args.tau, seed=args.seed),
    })
    write_json("ecg_date_audit.json", audit)

    sample = make_sample(df, args.per_site, args.seed, args.tau)
    sample_path = results_dir() / "ecg_manual_verification_sample.csv"
    sample.to_csv(sample_path, index=False)

    ev = offsets["ecg_minus_visit"]["overall"]
    print(f"\nHeaders readable ................. {extraction['n_header_readable']}")
    print(f"validation_date extracted ........ {extraction['date_extracted']['pct']}%  "
          f"failures: {extraction['failure_modes'] or 'none'}")
    print(f"base_date populated .............. {extraction['base_date_populated']['pct']}%")
    print(f"Distinct ECG dates ............... {date_distribution['n_distinct']} of {date_distribution['n_dates']} "
          f"(top date holds {date_distribution['share_top_1_pct']}%)")
    print("ECG − visit offsets (|days|):")
    for b in ev["bins"]:
        print(f"   {b['bin']:>9}: {b['k']:>5}  ({b['pct']}%)")
    print(f"ECG and CGM both within ±{args.tau} d of visit: {offsets['ecg_and_cgm_within_tau_of_visit']['pct']}%")
    print(f"Heuristic reading of validation_date: {interpretation['verdict']}  "
          f"({interpretation['fraction_within_tau_of_visit']*100:.1f}% within ±{args.tau} d)")
    date_keys = [f["key"] for f in inventory["fields"] if f["date_like"]]
    print(f"Date-like header fields found .... {date_keys}")
    print(f"\nManual verification sample ({len(sample)} records) → {sample_path}")
    print("Two people fill reviewer_*_parse_correct with Y/N, then run:")
    print(f"   python scripts/ecg_date_audit.py --score {sample_path}")


if __name__ == "__main__":
    main()

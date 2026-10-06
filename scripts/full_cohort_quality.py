#!/usr/bin/env python3
"""
full_cohort_quality.py — step 3 of the evidence pipeline (Reviewer 3,
comment 2; Reviewer 4).

The original Signal Quality module reported CGM and ECG statistics on the
first 200 / 150 participants in participants.tsv order. This script computes
the same statistics for EVERY participant with a parsed file, with 95% Wilson
confidence intervals, stratified by site and study group. It also quantifies
how far the old head-slice was from the full cohort, and computes the
readiness funnel (coverage → integrity → temporal gates).

Outputs
  results/quality_full.json   served by /api/eda/signal-quality and
                              /api/eda/readiness-funnel once present

Usage
  python scripts/full_cohort_quality.py [--tau 7] [--max-dropout 10]
                                        [--ecg-temporal auto|require|ignore]
"""

from __future__ import annotations

import argparse
import math

from _common import banner, load_readiness_table, provenance, read_json, write_json

HEAD_SLICE_CGM, HEAD_SLICE_ECG = 200, 150


def two_proportion_p(k1: int, n1: int, k2: int, n2: int) -> float | None:
    """Two-sided z-test p-value for p1 == p2 (pooled)."""
    if not n1 or not n2:
        return None
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (k1 / n1 - k2 / n2) / se
    return round(2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))), 4)


def holm(p_values: dict[str, float | None]) -> dict[str, float]:
    """Holm step-down adjustment for one family of tests."""
    items = sorted(((k, p) for k, p in p_values.items() if p is not None), key=lambda kv: kv[1])
    m, running, out = len(items), 0.0, {}
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = round(running, 4)
    return out


def records(df):
    cgm = df[df["cgm_dropout_pct"].notna()][["cgm_dropout_pct", "cgm_dropout_nominal_pct", "cgm_days"]]
    cgm_records = [
        {"dropout_pct": r.cgm_dropout_pct, "dropout_nominal_pct": r.cgm_dropout_nominal_pct, "days_covered": r.cgm_days}
        for r in cgm.itertuples()
    ]
    ecg = df[df["ecg_header_ok"] == True]  # noqa: E712
    ecg_records = [
        {"verdict": r.ecg_verdict if isinstance(r.ecg_verdict, str) else "unknown",
         "hr": None if math.isnan(r.ecg_hr) else int(r.ecg_hr),
         "qtc": None if math.isnan(r.ecg_qtc) else int(r.ecg_qtc)}
        for r in ecg[["ecg_verdict", "ecg_hr", "ecg_qtc"]].astype({"ecg_hr": float, "ecg_qtc": float}).itertuples()
    ]
    return cgm_records, ecg_records


def compact(summary: dict) -> dict:
    """Headline numbers only, for stratified tables."""
    c, e = summary["cgm"], summary["ecg"]
    out = {}
    if c:
        out.update({
            "cgm_n": c["n_sampled"], "cgm_mean_dropout_pct": c["mean_dropout_pct"],
            "cgm_pct_under_threshold": c["pct_under_threshold"],
            "cgm_pct_under_threshold_ci95": c["pct_under_threshold_ci95"],
            "cgm_mean_duration_days": c["mean_duration_days"],
        })
    if e:
        v = {x["verdict"]: x for x in e["verdicts"]}
        out.update({"ecg_n": e["n_sampled"], "ecg_mean_hr": e["mean_hr"], "ecg_mean_qtc": e["mean_qtc"]})
        for key in ("normal", "otherwise_normal", "borderline", "abnormal"):
            if key in v:
                out[f"ecg_pct_{key}"] = v[key]["pct"]
                out[f"ecg_pct_{key}_ci95"] = v[key]["ci95"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tau", type=int, default=7, help="co-registration tolerance (days)")
    ap.add_argument("--max-dropout", type=float, default=10.0, help="CGM integrity gate threshold (%%)")
    ap.add_argument("--ecg-temporal", choices=["auto", "require", "ignore"], default="auto",
                    help="include the ECG date in the temporal gate; 'auto' follows the date audit")
    args = ap.parse_args()

    from services.eda_service import ECG_PROVENANCE
    from services.readiness_service import (
        apply_gates, gate_funnel, stratified_sample, summarise_quality,
    )

    banner("Full-cohort signal quality and readiness funnel")
    df = load_readiness_table()
    n_flag_cgm, n_flag_ecg = int(df["flag_cgm"].sum()), int(df["flag_ecg"].sum())

    def summarise(sub, method):
        c, e = records(sub)
        return summarise_quality(c, e, sampling_method=method, n_total_cgm=n_flag_cgm,
                                 n_total_ecg=n_flag_ecg, max_dropout_pct=args.max_dropout)

    full = summarise(df, "full cohort: every participant with a parsed file")
    if full["ecg"]:
        full["ecg"].update(ECG_PROVENANCE)
        fw = df.loc[df["ecg_header_ok"] == True, "ecg_firmware"].fillna("(missing)").value_counts()  # noqa: E712
        full["ecg"]["firmware_observed"] = {k: int(v) for k, v in fw.items()}

    # Stratified tables
    by_site = {s: compact(summarise(g, s)) for s, g in df.groupby("clinical_site")}
    by_group = {s: compact(summarise(g, s)) for s, g in df.groupby("study_group")}
    by_site_group = [
        {"site": s, "study_group": grp, "n": len(g), **compact(summarise(g, f"{s}/{grp}"))}
        for (s, grp), g in df.groupby(["clinical_site", "study_group"])
    ]

    # Head-slice (the R1 manuscript's sample) vs a seeded random sample vs full cohort
    cgm_pool = df[df["flag_cgm"] == True]  # noqa: E712
    ecg_pool = df[df["flag_ecg"] == True]  # noqa: E712
    head = summarise(cgm_pool.head(HEAD_SLICE_CGM), "head-slice")["cgm"], \
        summarise(ecg_pool.head(HEAD_SLICE_ECG), "head-slice")["ecg"]
    rand = summarise(stratified_sample(cgm_pool, HEAD_SLICE_CGM, "study_group", 42), "random")["cgm"], \
        summarise(stratified_sample(ecg_pool, HEAD_SLICE_ECG, "study_group", 42), "random")["ecg"]

    # The head-slice is part of the full cohort, so it is compared with the
    # REMAINING participants (independent samples). The four ECG verdict tests
    # are Holm-adjusted as one family.
    cgm_head_rows, ecg_head_rows = cgm_pool.head(HEAD_SLICE_CGM), ecg_pool.head(HEAD_SLICE_ECG)
    rest = summarise(cgm_pool.drop(cgm_head_rows.index), "remainder")["cgm"], \
        summarise(ecg_pool.drop(ecg_head_rows.index), "remainder")["ecg"]

    def verdict_of(summary: dict, verdict: str) -> dict | None:
        return next((v for v in summary["verdicts"] if v["verdict"] == verdict), None)

    comparison = {}
    if head[0] and rest[0]:
        hn, rn = head[0]["n_sampled"], rest[0]["n_sampled"]
        hk = round(head[0]["pct_under_threshold"] / 100 * hn)
        rk = round(rest[0]["pct_under_threshold"] / 100 * rn)
        comparison["cgm_pct_under_threshold"] = {
            "head_slice": head[0]["pct_under_threshold"], "head_slice_ci95": head[0]["pct_under_threshold_ci95"],
            "remainder": rest[0]["pct_under_threshold"], "remainder_ci95": rest[0]["pct_under_threshold_ci95"],
            "full": full["cgm"]["pct_under_threshold"], "p_value": two_proportion_p(hk, hn, rk, rn)}
        comparison["cgm_mean_dropout_pct"] = {"head_slice": head[0]["mean_dropout_pct"],
                                              "remainder": rest[0]["mean_dropout_pct"],
                                              "random_sample": rand[0]["mean_dropout_pct"] if rand[0] else None,
                                              "full": full["cgm"]["mean_dropout_pct"]}
    if head[1] and rest[1]:
        family = {}
        for v in ("normal", "otherwise_normal", "borderline", "abnormal"):
            h, r, f = verdict_of(head[1], v), verdict_of(rest[1], v), verdict_of(full["ecg"], v)
            if not (h and r and f):
                continue
            comparison[f"ecg_pct_{v}"] = {
                "head_slice": h["pct"], "head_slice_ci95": h["ci95"],
                "remainder": r["pct"], "remainder_ci95": r["ci95"],
                "full": f["pct"], "full_ci95": f["ci95"],
                "p_value": two_proportion_p(h["k"], h["n"], r["k"], r["n"])}
            family[f"ecg_pct_{v}"] = comparison[f"ecg_pct_{v}"]["p_value"]
        for key, p_adj in holm(family).items():
            comparison[key]["p_holm"] = p_adj
        comparison["ecg_mean_qtc"] = {"head_slice": head[1]["mean_qtc"], "remainder": rest[1]["mean_qtc"],
                                      "random_sample": rand[1]["mean_qtc"] if rand[1] else None,
                                      "full": full["ecg"]["mean_qtc"]}
    head_composition = {
        "cgm_head_slice_by_site": {k: int(v) for k, v in cgm_head_rows["clinical_site"].value_counts().items()},
        "ecg_head_slice_by_site": {k: int(v) for k, v in ecg_head_rows["clinical_site"].value_counts().items()},
        "cgm_full_by_site":       {k: int(v) for k, v in cgm_pool["clinical_site"].value_counts().items()},
        "cgm_head_slice_by_group": {k: int(v) for k, v in cgm_head_rows["study_group"].value_counts().items()},
        "cgm_full_by_group":       {k: int(v) for k, v in cgm_pool["study_group"].value_counts().items()},
    }

    # Readiness funnel
    audit = read_json("ecg_date_audit.json")
    if args.ecg_temporal == "auto":
        verdict = (audit or {}).get("validation_date_interpretation", {}).get("verdict")
        ecg_temporal = verdict == "behaves_like_acquisition_date"
        ecg_temporal_reason = f"auto: date audit verdict = {verdict or 'audit not run'}"
    else:
        ecg_temporal = args.ecg_temporal == "require"
        ecg_temporal_reason = f"set explicitly: {args.ecg_temporal}"
    gates = apply_gates(df, tau_days=args.tau, max_dropout_pct=args.max_dropout, ecg_temporal=ecg_temporal)
    gates_alt = apply_gates(df, tau_days=args.tau, max_dropout_pct=args.max_dropout, ecg_temporal=not ecg_temporal)
    tau_sensitivity = [
        {"tau_days": t, "n_g3": int(apply_gates(df, tau_days=t, max_dropout_pct=args.max_dropout,
                                                 ecg_temporal=ecg_temporal)["G3"].sum())}
        for t in (0, 1, 3, 7, 14)
    ]

    payload = {
        "summary":               full,
        "by_site":               by_site,
        "by_group":              by_group,
        "by_site_group":         by_site_group,
        "head_slice_comparison": {"metrics": comparison, "composition": head_composition,
                                  "note": "head-slice = first 200 CGM / 150 ECG participants in participants.tsv order "
                                          "(the R1 manuscript's sample); remainder = all other participants; "
                                          "p = two-proportion z-test, head-slice vs remainder (independent samples); "
                                          "p_holm = Holm-adjusted across the four ECG verdicts"},
        "funnel":                gate_funnel(df, gates),
        "funnel_alternative_ecg_policy": {"ecg_temporal": not ecg_temporal, "funnel": gate_funnel(df, gates_alt)},
        "tau_sensitivity":       tau_sensitivity,
        "gate_params":           {"tau_days": args.tau, "max_cgm_dropout_pct": args.max_dropout,
                                  "ecg_temporal": ecg_temporal, "ecg_temporal_reason": ecg_temporal_reason},
        "_meta":                 provenance("full_cohort_quality.py", tau=args.tau, max_dropout=args.max_dropout,
                                            ecg_temporal=args.ecg_temporal),
    }
    write_json("quality_full.json", payload)

    c, e = full["cgm"], full["ecg"]
    if c:
        print(f"\nCGM  n={c['n_sampled']}  mean dropout {c['mean_dropout_pct']}%  "
              f"<{args.max_dropout:g}% dropout: {c['pct_under_threshold']}% {c['pct_under_threshold_ci95']}")
    if e:
        print(f"ECG  n={e['n_sampled']}  " + "  ".join(
            f"{v['verdict']} {v['pct']}% {v['ci95']}" for v in e["verdicts"]))
    print("\nHead-slice vs remaining participants:")
    for k, v in comparison.items():
        print(f"   {k:<28} {v}")
    print(f"\nReadiness funnel (ECG temporal gate: {ecg_temporal}; {ecg_temporal_reason}):")
    for row in payload["funnel"]:
        print(f"   {row['gate']}  {row['n']:>5}  ({row['pct_of_G0']}%)  {row['label']}")
    print("\nG3 by tolerance: " + ", ".join(f"tau={r['tau_days']}: {r['n_g3']}" for r in tau_sensitivity))
    print("\nWrote results/quality_full.json — the dashboard now serves full-cohort numbers.")


if __name__ == "__main__":
    main()

"""End-to-end run of the evidence pipeline on the synthetic dataset."""

import json

import pandas as pd


def _load(results, name):
    return json.loads((results / name).read_text())


def test_evidence_pipeline_end_to_end(synthetic_env, run_script, client):
    results = synthetic_env["results"]

    run_script("build_readiness_table.py", "--workers", "4")
    table = pd.read_csv(results / "participant_readiness.csv", dtype={"person_id": str})
    summary = _load(results, "readiness_table_summary.json")
    assert len(table) == summary["n_participants"] == 160
    assert summary["_meta"]["synthetic"] is True

    run_script("ecg_date_audit.py", "--per-site", "5")
    audit = _load(results, "ecg_date_audit.json")
    ex = audit["extraction"]
    # the fixture plants missing and malformed validation_date values
    assert ex["date_extracted"]["pct"] < 100
    assert set(ex["failure_modes"]) <= {"missing", "malformed", "no_hea_file", "header_read_error"}
    assert ex["base_date_populated"]["pct"] == 0.0
    assert audit["date_distribution"]["top_dates"][0]["n"] >= 1
    assert any(f["key"] == "validation_date" and f["date_like"] for f in audit["field_inventory"]["fields"])
    sample = pd.read_csv(results / "ecg_manual_verification_sample.csv", dtype=str)
    assert set(sample["clinical_site"]) == {"UW", "UCSD", "UAB"}

    # Scoring the manual check: both reviewers agree with the parser everywhere
    sample["reviewer_1_parse_correct"] = "Y"
    sample["reviewer_2_parse_correct"] = "Y"
    filled = results / "filled.csv"
    sample.to_csv(filled, index=False)
    run_script("ecg_date_audit.py", "--score", str(filled))
    mv = _load(results, "ecg_date_audit.json")["manual_verification"]
    assert mv["both_correct"]["pct"] == 100.0 and mv["n_scored"] == len(sample)

    run_script("full_cohort_quality.py")
    quality = _load(results, "quality_full.json")
    assert quality["summary"]["cgm"]["n_sampled"] == int(table["cgm_dropout_pct"].notna().sum())
    assert quality["summary"]["ecg"]["n_sampled"] == int(table["ecg_header_ok"].sum())
    assert [r["gate"] for r in quality["funnel"]] == ["G0", "G1", "G2", "G3"]
    ns = [r["n"] for r in quality["funnel"]]
    assert ns == sorted(ns, reverse=True)
    # First-N is compared with the remaining participants, Holm-adjusted
    cmp_ = quality["head_slice_comparison"]["metrics"]
    for v in ("normal", "otherwise_normal", "borderline", "abnormal"):
        assert "remainder" in cmp_[f"ecg_pct_{v}"]
        assert cmp_[f"ecg_pct_{v}"]["p_holm"] >= cmp_[f"ecg_pct_{v}"]["p_value"]
    taus = [r["n_g3"] for r in quality["tau_sensitivity"]]
    assert len(taus) == 5 and taus == sorted(taus)  # G3 grows with tolerance

    run_script("gating_experiment.py", "--bootstrap", "50", "--rand-repeats", "3")
    gating = _load(results, "gating_results.json")
    dx = gating["tasks"]["diagnosis_t2d"]
    assert set(dx["conditions"]) == {"logreg", "hgb"}
    assert dx["conditions"]["hgb"]["G0"]["n_train"] >= dx["conditions"]["hgb"]["G3"]["n_train"]
    used = gating["features"]["ECG"] + gating["features"]["CGM"] + gating["features"]["Clinical"]
    assert "hba1c" not in used  # no label leakage

    run_script("benchmark_api.py", "--repeats", "2")
    bench = _load(results, "benchmark.json")
    assert bench["steps"]["1 cohort scoping"]["status"] == 200
    assert bench["manual_baseline"]["analysis_loc"] > 0

    usability = results / "usability.csv"
    usability.write_text(
        "participant,background,t1_time_s,t1_outcome,t2_time_s,t2_outcome,t3_time_s,t3_outcome,"
        "t4_time_s,t4_outcome,t5_time_s,t5_outcome,sus1,sus2,sus3,sus4,sus5,sus6,sus7,sus8,sus9,sus10,"
        "u1_time_saving,u2_trust,comment\n"
        "P1,clinical,40,S,60,S,90,A,120,S,30,S,5,1,5,1,5,1,5,1,5,1,5,4,\n"
        "P2,data-science,35,S,50,S,70,S,100,S,25,S,4,2,4,2,4,2,4,2,4,2,4,4,\n")
    run_script("score_usability.py", str(usability))
    u = _load(results, "usability.json")
    assert u["sus"]["mean"] == 87.5  # (100 + 75) / 2

    run_script("make_paper_assets.py")
    paper = results / "paper"
    for name in ("tab_quality.tex", "tab_date_audit.tex", "tab_gating.tex", "tab_benchmark.tex",
                 "tab_usability.tex", "fig_offsets.pdf", "fig_gating.pdf", "fig_funnel.pdf", "numbers.md"):
        assert (paper / name).exists(), name
    assert "SYNTHETIC" in (paper / "numbers.md").read_text()

    # The API now serves the precomputed full-cohort results
    q = client.get("/api/eda/signal-quality").json()
    assert q["source"] == "precomputed_full_cohort"
    assert client.get("/api/eda/temporal-offsets").status_code == 200
    funnel = client.get("/api/eda/readiness-funnel").json()["funnel"]
    assert funnel[0]["gate"] == "G0"

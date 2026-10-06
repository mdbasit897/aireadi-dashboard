from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from services.readiness_service import (
    apply_gates,
    bin_offsets,
    classify_philips_verdict,
    comments_to_dict,
    gate_funnel,
    interpret_validation_date,
    offset_bin,
    parse_yyyymmdd,
    stratified_sample,
    summarise_cgm,
    wilson_ci,
)


@pytest.mark.parametrize("text,expected", [
    ("- NORMAL ECG -", "normal"),
    ("- OTHERWISE NORMAL ECG -", "otherwise_normal"),
    ("- BORDERLINE ECG -", "borderline"),
    ("- ABNORMAL ECG -", "abnormal"),
    ("", "unknown"),
    (None, "unknown"),
    ("something else", "unknown"),
])
def test_classify_philips_verdict(text, expected):
    assert classify_philips_verdict(text) == expected


@pytest.mark.parametrize("value,expected", [
    ("20241014", (date(2024, 10, 14), None)),
    ("", (None, "missing")),
    (None, (None, "missing")),
    ("2024-10-14", (None, "malformed")),
    ("20241399", (None, "malformed")),
    ("2024101", (None, "malformed")),
])
def test_parse_yyyymmdd(value, expected):
    assert parse_yyyymmdd(value) == expected


def test_comments_to_dict_splits_at_first_colon():
    d = comments_to_dict(["validation_date: 20241014", "note: a: b", "no colon here"])
    assert d == {"validation_date": "20241014", "note": "a: b"}


def test_wilson_ci_known_values():
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0 and hi == pytest.approx(27.8, abs=0.1)
    lo, hi = wilson_ci(50, 100)
    assert lo == pytest.approx(40.4, abs=0.1) and hi == pytest.approx(59.6, abs=0.1)
    assert wilson_ci(0, 0) == (None, None)


@pytest.mark.parametrize("days,label", [(0, "same day"), (-3, "1–7 d"), (7, "1–7 d"), (8, "8–30 d"),
                                        (31, "31–365 d"), (-400, ">365 d"), (None, None)])
def test_offset_bin(days, label):
    assert offset_bin(days) == label


def test_bin_offsets_counts_and_signs():
    out = bin_offsets([0, 0, 2, -5, 40, None])
    assert out["n"] == 5
    assert {b["bin"]: b["k"] for b in out["bins"]} == {"same day": 2, "1–7 d": 2, "8–30 d": 0,
                                                      "31–365 d": 1, ">365 d": 0}
    assert out["n_before_anchor"] == 1 and out["n_after_anchor"] == 2


def test_summarise_cgm_dropout_definitions():
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # 2 days of 5-min slots with every 10th reading missing → ~10% dropout over the observed span
    stamps = [t0 + timedelta(minutes=5 * i) for i in range(2 * 288 + 1) if i % 10 != 5]
    out = summarise_cgm(stamps, [120.0] * len(stamps))
    assert out["days_covered"] == pytest.approx(2.0, abs=0.01)
    assert out["dropout_pct"] == pytest.approx(10.0, abs=0.5)
    # against the nominal 10-day wear the same recording is mostly missing
    assert out["dropout_nominal_pct"] > 75
    assert out["tir_pct"] == 100.0 and out["gmi_pct"] == pytest.approx(3.31 + 0.02392 * 120, abs=0.01)
    assert summarise_cgm([], []) is None


def _table():
    return pd.DataFrame({
        "person_id":       ["a", "b", "c", "d", "e"],
        "study_group":     ["x", "x", "y", "y", "y"],
        "has_ecg_file":    [True, True, True, False, True],
        "has_cgm_file":    [True, True, True, True, True],
        "has_clinical":    [True, True, True, True, True],
        "ecg_header_ok":   [True, True, True, False, True],
        "cgm_dropout_pct": [1.0, 25.0, 2.0, 1.0, 3.0],
        "cgm_offset_days": [0, 0, 12, 0, 1],
        "ecg_offset_days": [0, 0, 0, None, 30],
    })


def test_apply_gates_cumulative():
    df = _table()
    g = apply_gates(df, tau_days=7, max_dropout_pct=10)
    assert g["G0"].tolist() == [True] * 5
    assert g["G1"].tolist() == [True, True, True, False, True]
    assert g["G2"].tolist() == [True, False, True, False, True]
    assert g["G3"].tolist() == [True, False, False, False, True]
    g_ecg = apply_gates(df, tau_days=7, max_dropout_pct=10, ecg_temporal=True)
    assert g_ecg["G3"].tolist() == [True, False, False, False, False]
    funnel = gate_funnel(df, g)
    assert [r["n"] for r in funnel] == [5, 4, 3, 2]
    assert funnel[-1]["by_group"]["x"]["n"] == 1


def test_stratified_sample_is_proportional_and_seeded():
    df = pd.DataFrame({"g": ["a"] * 60 + ["b"] * 30 + ["c"] * 10, "v": range(100)})
    s1 = stratified_sample(df, 20, "g", seed=1)
    s2 = stratified_sample(df, 20, "g", seed=1)
    assert len(s1) == 20 and s1.index.tolist() == s2.index.tolist()
    assert s1["g"].value_counts().to_dict() == {"a": 12, "b": 6, "c": 2}


def test_interpret_validation_date():
    near = {"n": 100, "bins": [{"bin": "same day", "k": 85}, {"bin": "1–7 d", "k": 5}]}
    far = {"n": 100, "bins": [{"bin": "same day", "k": 3}, {"bin": "1–7 d", "k": 2}]}
    assert interpret_validation_date(near, 90, 100)["verdict"] == "behaves_like_acquisition_date"
    assert interpret_validation_date(far, 3, 100)["verdict"] == "behaves_like_processing_date"
    assert interpret_validation_date({"n": 0, "bins": []}, 0, 0)["verdict"] == "insufficient_data"

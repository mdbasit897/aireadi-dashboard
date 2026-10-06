"""API tests on the synthetic dataset, before the offline pipeline has run."""

import pytest

from services.eda_service import _parse_ecg_comments


def test_app_imports_and_all_routers_register(client):
    # Regression: v1.1 failed at import because services/__init__.py imported
    # get_ecg_data from an ecg_service.py that had been overwritten.
    paths = {r.path for r in client.app.routes}
    for p in ("/api/patients/{person_id}/ecg", "/api/eda/signal-quality",
              "/api/eda/temporal-offsets", "/api/eda/readiness-funnel"):
        assert p in paths
    assert client.get("/api/health").json()["status"] == "ok"


def test_ecg_waveform_endpoint_returns_12_leads(client):
    pid = next(p["person_id"] for p in client.get("/api/patients?page_size=50").json()["participants"]
               if p["has_ecg"] and client.get(f"/api/patients/{p['person_id']}/ecg").status_code == 200)
    ecg = client.get(f"/api/patients/{pid}/ecg").json()
    assert len(ecg["leads"]) == 12 and ecg["fs"] == 500


def test_verdict_uses_interpretation_comment_2_not_keywords():
    # A secondary annotation mentioning ST elevation on an OTHERWISE NORMAL
    # record must not raise the abnormal flag (the old keyword logic did).
    meta = _parse_ecg_comments([
        "validation_date: 20241014",
        "comment_3_key: Minimal ST elevation, anterior leads",
        "interpretation_comment_2: - OTHERWISE NORMAL ECG -",
    ])
    assert meta["ecg_verdict"] == "otherwise_normal"
    assert meta["has_abnormal_flag"] is False
    assert meta["recording_date"] == "2024-10-14"
    abnormal = _parse_ecg_comments(["interpretation_comment_2: - ABNORMAL ECG -"])
    assert abnormal["has_abnormal_flag"] is True and abnormal["recording_date_failure"] == "missing"


def test_signal_quality_live_sample_is_stratified_and_four_way(client):
    q = client.get("/api/eda/signal-quality?source=sample").json()
    assert q["source"] == "live_sample"
    assert "stratified" in q["cgm"]["sampling_method"]
    verdicts = {v["verdict"] for v in q["ecg"]["verdicts"]}
    assert {"normal", "otherwise_normal", "borderline", "abnormal"} <= verdicts
    for v in q["ecg"]["verdicts"]:
        lo, hi = v["ci95"]
        assert lo <= v["pct"] <= hi


def test_precomputed_endpoints_404_before_pipeline(client, tmp_path, monkeypatch):
    from config import get_settings

    monkeypatch.setattr(get_settings(), "results_dir", str(tmp_path))
    assert client.get("/api/eda/temporal-offsets").status_code == 404
    assert client.get("/api/eda/readiness-funnel").status_code == 404
    assert client.get("/api/eda/signal-quality?source=precomputed").status_code == 404
    assert client.get("/api/eda/signal-quality").json()["source"] == "live_sample"


def test_participant_timeline_reports_offsets(client):
    pid = client.get("/api/patients?page_size=1").json()["participants"][0]["person_id"]
    t = client.get(f"/api/eda/temporal-overlap/{pid}?tau_days=7").json()
    assert t["tau_days"] == 7
    if t["cgm_start"] and t["visit_date"]:
        assert isinstance(t["cgm_offset_days"], int)
        assert t["cgm_co_registered"] == (abs(t["cgm_offset_days"]) <= 7)

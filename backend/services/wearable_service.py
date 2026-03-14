"""
Wearable service — reads Garmin Vivosmart 5 data (heart rate, SpO2,
physical activity, stress, sleep, respiratory rate) in Open mHealth format.
"""
import os
import glob
import json
import statistics
from typing import Any

from config import get_settings

MODALITIES = {
    "heart_rate": "heart_rate",
    "oxygen_saturation": "oxygen_saturation",
    "physical_activity": "physical_activity",
    "stress": "stress",
    "sleep": "sleep",
    "respiratory_rate": "respiratory_rate",
}


def _load_json_files(directory: str) -> list[dict]:
    records = []
    for fp in glob.glob(os.path.join(directory, "**", "*.json"), recursive=True):
        try:
            with open(fp) as f:
                data = json.load(f)
            if isinstance(data, list):
                records.extend(data)
            else:
                records.append(data)
        except Exception:
            pass
    return records


def get_wearable_summary(person_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    base = settings.wearable_dir

    result: dict[str, Any] = {"person_id": person_id}

    # ── Heart rate ─────────────────────────────────────────────────────────
    hr_dir = os.path.join(base, "heart_rate", "garmin_vivosmart5", person_id)
    hr_values = []
    if os.path.isdir(hr_dir):
        for rec in _load_json_files(hr_dir):
            body = rec.get("body", rec)
            hr = body.get("heart_rate", {})
            v = hr.get("value") if isinstance(hr, dict) else None
            if v is not None:
                hr_values.append(float(v))
    result["mean_hr"] = round(statistics.mean(hr_values), 1) if hr_values else None

    # ── SpO2 ───────────────────────────────────────────────────────────────
    spo2_dir = os.path.join(base, "oxygen_saturation", "garmin_vivosmart5", person_id)
    spo2_values = []
    if os.path.isdir(spo2_dir):
        for rec in _load_json_files(spo2_dir):
            body = rec.get("body", rec)
            spo2 = body.get("oxygen_saturation", {})
            v = spo2.get("value") if isinstance(spo2, dict) else None
            if v is not None:
                spo2_values.append(float(v))
    result["mean_spo2"] = round(statistics.mean(spo2_values), 1) if spo2_values else None

    # ── Physical activity (steps) ─────────────────────────────────────────
    act_dir = os.path.join(base, "physical_activity", "garmin_vivosmart5", person_id)
    daily_steps: dict[str, float] = {}
    if os.path.isdir(act_dir):
        for rec in _load_json_files(act_dir):
            body = rec.get("body", rec)
            steps = body.get("step_count", {})
            ts = body.get("effective_time_frame", {}).get("date_time", "")
            day = ts[:10] if ts else ""
            v = steps.get("value") if isinstance(steps, dict) else None
            if v is not None and day:
                daily_steps[day] = daily_steps.get(day, 0) + float(v)
    result["mean_steps_per_day"] = (
        round(statistics.mean(daily_steps.values()), 0) if daily_steps else None
    )
    result["days_covered"] = len(daily_steps)

    # ── Stress ────────────────────────────────────────────────────────────
    stress_dir = os.path.join(base, "stress", "garmin_vivosmart5", person_id)
    stress_values = []
    if os.path.isdir(stress_dir):
        for rec in _load_json_files(stress_dir):
            body = rec.get("body", rec)
            s = body.get("stress_score", {})
            v = s.get("value") if isinstance(s, dict) else None
            if v is not None:
                stress_values.append(float(v))
    result["mean_stress"] = round(statistics.mean(stress_values), 1) if stress_values else None

    # ── Sleep ─────────────────────────────────────────────────────────────
    sleep_dir = os.path.join(base, "sleep", "garmin_vivosmart5", person_id)
    sleep_hours_list = []
    if os.path.isdir(sleep_dir):
        for rec in _load_json_files(sleep_dir):
            body = rec.get("body", rec)
            dur = body.get("total_sleep_time", {})
            v = dur.get("value") if isinstance(dur, dict) else None
            unit = dur.get("unit", "min") if isinstance(dur, dict) else "min"
            if v is not None:
                hours = float(v) / 60 if unit in ("min", "minutes") else float(v)
                sleep_hours_list.append(hours)
    result["sleep_hours"] = (
        round(statistics.mean(sleep_hours_list), 1) if sleep_hours_list else None
    )

    # Return None if no data at all
    has_any = any(v is not None for k, v in result.items() if k != "person_id")
    return result if has_any else None

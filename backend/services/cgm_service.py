"""
CGM service — reads Dexcom G6 Open mHealth JSON files and computes
Time-in-Range (TIR) metrics per participant.

Expected file path pattern:
  {cgm_dir}/{person_id}/continuous_glucose_monitoring/dexcom_g6/*.json
"""
import json
import os
import glob
from typing import Any

from config import get_settings

# Clinical glucose thresholds (mg/dL)
VERY_LOW  = 54
LOW       = 70
HIGH      = 180
VERY_HIGH = 250


def _find_cgm_files(person_id: str) -> list[str]:
    settings = get_settings()
    pattern = os.path.join(
        settings.cgm_dir, person_id, "**", "*.json"
    )
    files = glob.glob(pattern, recursive=True)
    if not files:
        # Also try flat structure
        pattern2 = os.path.join(settings.cgm_dir, f"{person_id}*.json")
        files = glob.glob(pattern2)
    return sorted(files)


def _parse_omh_glucose(file_path: str) -> list[dict]:
    """Parse Open mHealth blood_glucose JSON records."""
    readings = []
    try:
        with open(file_path) as f:
            data = json.load(f)

        # Open mHealth schema: data may be a list or a dict with a 'body' key
        records = data if isinstance(data, list) else data.get("body", [data])

        for rec in records:
            # blood_glucose schema
            bg = rec.get("blood_glucose") or rec.get("body", {}).get("blood_glucose")
            ts = (
                rec.get("effective_time_frame", {}).get("date_time")
                or rec.get("body", {}).get("effective_time_frame", {}).get("date_time")
            )
            if bg and ts:
                val = bg.get("value")
                unit = bg.get("unit", "mg/dL")
                if val is not None and unit in ("mg/dL", "mg_per_dL"):
                    readings.append({"timestamp": ts, "glucose_mg_dl": float(val)})
    except Exception:
        pass
    return readings


def get_cgm_data(person_id: str) -> dict[str, Any] | None:
    files = _find_cgm_files(person_id)
    if not files:
        return None

    all_readings = []
    for f in files:
        all_readings.extend(_parse_omh_glucose(f))

    if not all_readings:
        return None

    # Sort by timestamp
    all_readings.sort(key=lambda x: x["timestamp"])

    values = [r["glucose_mg_dl"] for r in all_readings if r["glucose_mg_dl"] is not None]
    n = len(values)
    if n == 0:
        return None

    # TIR calculations
    tir_pct        = round(sum(1 for v in values if LOW <= v <= HIGH)  / n * 100, 1)
    tir_low_pct    = round(sum(1 for v in values if v < LOW)           / n * 100, 1)
    tir_high_pct   = round(sum(1 for v in values if v > HIGH)          / n * 100, 1)
    tir_vhigh_pct  = round(sum(1 for v in values if v > VERY_HIGH)     / n * 100, 1)

    mean_g = round(sum(values) / n, 1)
    import statistics
    std_g = round(statistics.stdev(values) if n > 1 else 0.0, 1)

    # Days covered
    from datetime import datetime
    try:
        t0 = datetime.fromisoformat(all_readings[0]["timestamp"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(all_readings[-1]["timestamp"].replace("Z", "+00:00"))
        days = round((t1 - t0).total_seconds() / 86400, 1)
    except Exception:
        days = 0.0

    # Downsample series for chart (max 2000 points)
    series = all_readings
    if len(series) > 2000:
        step = len(series) // 2000
        series = series[::step]

    return {
        "person_id": person_id,
        "tir_pct": tir_pct,
        "tir_low_pct": tir_low_pct,
        "tir_high_pct": tir_high_pct,
        "tir_very_high_pct": tir_vhigh_pct,
        "mean_glucose": mean_g,
        "std_glucose": std_g,
        "readings_count": n,
        "days_covered": days,
        "series": series,
    }

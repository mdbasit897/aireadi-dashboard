"""
CGM service — reads Dexcom G6 Open mHealth JSON files and computes
Time-in-Range (TIR) metrics per participant.

Actual file path (AI-READI v3.0.0):
  {dataset_root}/wearable_blood_glucose/continuous_glucose_monitoring/dexcom_g6/{person_id}/{person_id}_DEX.json

Actual JSON schema:
  {
    "header": { ... },
    "body": {
      "cgm": [
        {
          "effective_time_frame": {
            "time_interval": {
              "start_date_time": "2023-07-27T23:51:43Z",
              "end_date_time":   "2023-07-27T23:51:43Z"
            }
          },
          "event_type": "EGV",
          "blood_glucose": { "unit": "mg/dL", "value": 113 }
        },
        ...
      ]
    }
  }
"""
import json
import os
import glob
import statistics
from datetime import datetime
from typing import Any

from config import get_settings

# Clinical glucose thresholds (mg/dL)
VERY_LOW  = 54
LOW       = 70
HIGH      = 180
VERY_HIGH = 250


def _find_cgm_files(person_id: str) -> list[str]:
    settings = get_settings()

    # Primary: confirmed AI-READI v3 layout
    primary = os.path.join(
        settings.dataset_root,
        "wearable_blood_glucose",
        "continuous_glucose_monitoring",
        "dexcom_g6",
        person_id,
        f"{person_id}_DEX.json",
    )
    if os.path.exists(primary):
        return [primary]

    # Fallback 1: any JSON under the participant's dexcom_g6 folder
    fallback1 = glob.glob(os.path.join(
        settings.dataset_root,
        "wearable_blood_glucose",
        "continuous_glucose_monitoring",
        "dexcom_g6",
        person_id,
        "*.json",
    ))
    if fallback1:
        return sorted(fallback1)

    # Fallback 2: legacy cgm_dir config path
    fallback2 = glob.glob(
        os.path.join(settings.cgm_dir, person_id, "**", "*.json"),
        recursive=True,
    )
    if fallback2:
        return sorted(fallback2)

    return []


def _parse_omh_glucose(file_path: str) -> list[dict]:
    """
    Parse AI-READI Dexcom G6 JSON.

    Each entry in body.cgm[] contains:
      - effective_time_frame.time_interval.start_date_time  (primary)
      - effective_time_frame.date_time                      (fallback)
      - blood_glucose.value  (numeric)
      - blood_glucose.unit   ("mg/dL")
    """
    readings = []
    try:
        with open(file_path) as f:
            data = json.load(f)

        cgm_list = data.get("body", {}).get("cgm", [])

        # Handle edge case: flat list at root level
        if not cgm_list and isinstance(data, list):
            cgm_list = data

        for entry in cgm_list:
            # --- timestamp ---
            tf = entry.get("effective_time_frame", {})
            ts = (
                tf.get("date_time")
                or tf.get("time_interval", {}).get("start_date_time")
            )

            # --- glucose value ---
            bg   = entry.get("blood_glucose", {})
            val  = bg.get("value")
            unit = bg.get("unit", "mg/dL")

            if ts is None or val is None:
                continue

            # Normalise units
            if unit in ("mg/dL", "mg_per_dL", "mg/dl"):
                readings.append({"timestamp": ts, "glucose_mg_dl": float(val)})
            elif unit in ("mmol/L", "mmol/l"):
                # Convert mmol/L → mg/dL
                readings.append({"timestamp": ts, "glucose_mg_dl": round(float(val) * 18.015, 1)})

    except Exception:
        pass

    return readings


def get_cgm_data(person_id: str) -> dict[str, Any] | None:
    files = _find_cgm_files(person_id)
    if not files:
        return None

    all_readings: list[dict] = []
    for f in files:
        all_readings.extend(_parse_omh_glucose(f))

    if not all_readings:
        return None

    # Sort chronologically by timestamp string (ISO format sorts lexicographically)
    all_readings.sort(key=lambda x: x["timestamp"])

    values = [r["glucose_mg_dl"] for r in all_readings if r["glucose_mg_dl"] is not None]
    n = len(values)
    if n == 0:
        return None

    # ── TIR calculations ─────────────────────────────────────────────────────
    tir_pct       = round(sum(1 for v in values if LOW <= v <= HIGH) / n * 100, 1)
    tir_low_pct   = round(sum(1 for v in values if v < LOW)          / n * 100, 1)
    tir_high_pct  = round(sum(1 for v in values if v > HIGH)         / n * 100, 1)
    tir_vhigh_pct = round(sum(1 for v in values if v > VERY_HIGH)    / n * 100, 1)

    mean_g = round(sum(values) / n, 1)
    std_g  = round(statistics.stdev(values) if n > 1 else 0.0, 1)

    # ── Days covered ─────────────────────────────────────────────────────────
    try:
        t0   = datetime.fromisoformat(all_readings[0]["timestamp"].replace("Z", "+00:00"))
        t1   = datetime.fromisoformat(all_readings[-1]["timestamp"].replace("Z", "+00:00"))
        days = round((t1 - t0).total_seconds() / 86400, 1)
    except Exception:
        days = 0.0

    # ── Downsample for chart (max 2000 points) ────────────────────────────────
    series = all_readings
    if len(series) > 2000:
        step   = len(series) // 2000
        series = series[::step]

    return {
        "person_id":        person_id,
        "tir_pct":          tir_pct,
        "tir_low_pct":      tir_low_pct,
        "tir_high_pct":     tir_high_pct,
        "tir_very_high_pct": tir_vhigh_pct,
        "mean_glucose":     mean_g,
        "std_glucose":      std_g,
        "readings_count":   n,
        "days_covered":     days,
        "series":           series,
    }
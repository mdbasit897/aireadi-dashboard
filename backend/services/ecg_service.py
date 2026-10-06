"""
ECG service — reads 12-lead ECG data in WFDB format from the Philips TC30 device.

Expected path pattern:
  {ecg_dir}/{person_id}/*.hea  (WFDB header + dat pair)
"""
import os
import glob
from typing import Any

import numpy as np

from config import get_settings

LEAD_NAMES = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
# Max samples to send to frontend (10 seconds @ 500 Hz = 5000 pts per lead)
MAX_SAMPLES = 5000


def _find_wfdb_record(person_id: str) -> str | None:
    settings = get_settings()
    # Try participant sub-directory
    pattern = os.path.join(settings.ecg_dir, person_id, "*.hea")
    headers = glob.glob(pattern)
    if not headers:
        # Flat layout
        pattern2 = os.path.join(settings.ecg_dir, f"{person_id}*.hea")
        headers = glob.glob(pattern2)
    if not headers:
        return None
    # Return record name (path without .hea); sorted so the choice is
    # deterministic when a participant has more than one recording
    return sorted(headers)[0][: -len(".hea")]


def get_ecg_data(person_id: str) -> dict[str, Any] | None:
    record_path = _find_wfdb_record(person_id)
    if not record_path:
        return None

    try:
        import wfdb
        record = wfdb.rdrecord(record_path)
    except Exception:
        return None

    fs = record.fs
    duration_sec = record.sig_len / fs

    # Use signal names from record if available, else fall back to standard order
    sig_names = record.sig_name if record.sig_name else LEAD_NAMES[: record.n_sig]

    leads = []
    for i in range(record.n_sig):
        signal = record.p_signal[:, i]
        # Remove NaN
        signal = np.where(np.isnan(signal), 0.0, signal)
        # Downsample if needed — take first 10 seconds for display
        if len(signal) > MAX_SAMPLES:
            signal = signal[:MAX_SAMPLES]
        leads.append({
            "name": sig_names[i] if i < len(sig_names) else f"Lead {i+1}",
            "signal": [round(float(v), 4) for v in signal],
        })

    return {
        "person_id": person_id,
        "fs": fs,
        "duration_sec": round(duration_sec, 2),
        "leads": leads,
        "units": record.units[0] if record.units else "mV",
    }

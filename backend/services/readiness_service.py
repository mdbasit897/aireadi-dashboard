"""
Readiness service — shared helpers for the three readiness axes:

  1. Coverage                 — does a participant have the required files?
  2. Temporal co-registration — were the streams captured close in time?
  3. Signal integrity         — is each stream usable without further curation?

These functions are deliberately free of filesystem access so that the live
API (services/eda_service.py) and the offline evidence scripts (scripts/)
compute every reported number through the same code path.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timezone
from typing import Any, Iterable

import pandas as pd

# ── Constants ────────────────────────────────────────────────────────────────

CGM_READINGS_PER_DAY = 288          # Dexcom G6: one estimated glucose value / 5 min
NOMINAL_CGM_WEAR_DAYS = 10          # Dexcom G6 sensor life
DEFAULT_TAU_DAYS = 7                # temporal co-registration tolerance (days)
DEFAULT_MAX_CGM_DROPOUT_PCT = 10.0  # integrity gate threshold

# Glucose thresholds (mg/dL), international consensus on time-in-range
TBR_LIMIT = 70
TAR_LIMIT = 180

# Offset bins on |offset| in days (lower bound inclusive, upper bound inclusive)
OFFSET_BINS: list[tuple[str, int, float]] = [
    ("same day", 0, 0),
    ("1–7 d", 1, 7),
    ("8–30 d", 8, 30),
    ("31–365 d", 31, 365),
    (">365 d", 366, math.inf),
]

VERDICTS = ("normal", "otherwise_normal", "borderline", "abnormal", "unknown")
VERDICT_LABELS = {
    "normal":           "Normal ECG",
    "otherwise_normal": "Otherwise normal ECG",
    "borderline":       "Borderline ECG",
    "abnormal":         "Abnormal ECG",
    "unknown":          "No verdict",
}


# ── ECG header helpers ───────────────────────────────────────────────────────

def comments_to_dict(comments: Iterable[str]) -> dict[str, str]:
    """`key: value` WFDB comment lines → dict (first ':' splits key from value)."""
    meta: dict[str, str] = {}
    for c in comments or []:
        if ":" in c:
            key, _, val = c.partition(":")
            meta[key.strip()] = val.strip()
    return meta


def parse_yyyymmdd(value: str | None) -> tuple[date | None, str | None]:
    """
    Parse a bare YYYYMMDD string.

    Returns (date, None) on success or (None, failure_reason) where the
    reason is one of "missing" or "malformed".
    """
    if value is None or str(value).strip() == "":
        return None, "missing"
    v = str(value).strip()
    if len(v) != 8 or not v.isdigit():
        return None, "malformed"
    try:
        return datetime.strptime(v, "%Y%m%d").date(), None
    except ValueError:
        return None, "malformed"


def classify_philips_verdict(text: str | None) -> str:
    """
    Map the Philips PageWriter TC30 `interpretation_comment_2` field to one of
    the four machine verdicts. "OTHERWISE NORMAL ECG" must be tested before
    "ABNORMAL ECG"/"NORMAL ECG" because it contains both substrings' letters.
    """
    t = (text or "").strip().upper()
    if not t:
        return "unknown"
    if "OTHERWISE NORMAL" in t:
        return "otherwise_normal"
    if "BORDERLINE" in t:
        return "borderline"
    if "ABNORMAL ECG" in t:
        return "abnormal"
    if "NORMAL ECG" in t:
        return "normal"
    return "unknown"


def to_int_or_none(value: Any) -> int | None:
    try:
        v = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


# ── CGM helpers ──────────────────────────────────────────────────────────────

def cgm_readings_from_omh(doc: dict) -> tuple[list[datetime], list[float]]:
    """
    Extract (timestamps, glucose mg/dL) from an AI-READI Dexcom G6 Open mHealth
    document. Entries without a timestamp are skipped; entries without a value
    still count as timestamps (they occupy a 5-minute slot).
    """
    entries = doc.get("body", {}).get("cgm", []) if isinstance(doc, dict) else []
    stamps: list[datetime] = []
    values: list[float] = []
    for e in entries:
        tf = e.get("effective_time_frame", {})
        ts = tf.get("date_time") or tf.get("time_interval", {}).get("start_date_time")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        stamps.append(t)
        bg = e.get("blood_glucose", {})
        val, unit = bg.get("value"), bg.get("unit", "mg/dL")
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        values.append(v * 18.015 if unit in ("mmol/L", "mmol/l") else v)
    return stamps, values


def summarise_cgm(stamps: list[datetime], values: list[float]) -> dict[str, Any] | None:
    """
    Window, dropout and glycaemic summary for one CGM recording.

    Two dropout definitions are reported:
      dropout_pct          — against the observed span (first → last reading);
                             blind to gaps at either end of the wear period.
      dropout_nominal_pct  — against the nominal 10-day Dexcom G6 wear period.
    """
    if not stamps:
        return None
    stamps = sorted(stamps)
    t0, t1 = stamps[0], stamps[-1]
    days = (t1 - t0).total_seconds() / 86400
    n = len(stamps)

    expected = max(1.0, days * CGM_READINGS_PER_DAY)
    expected_nominal = NOMINAL_CGM_WEAR_DAYS * CGM_READINGS_PER_DAY

    out: dict[str, Any] = {
        "cgm_start":           t0.date().isoformat(),   # calendar date, UTC
        "cgm_end":             t1.date().isoformat(),   # calendar date, UTC
        "cgm_start_utc_hour":  t0.astimezone(timezone.utc).hour if t0.tzinfo else t0.hour,
        "days_covered":        round(days, 1),
        "n_readings":          n,
        "dropout_pct":         round(max(0.0, (expected - n) / expected) * 100, 1),
        "dropout_nominal_pct": round(max(0.0, (expected_nominal - n) / expected_nominal) * 100, 1),
    }

    if values:
        s = pd.Series(values, dtype=float)
        mean = float(s.mean())
        sd = float(s.std(ddof=1)) if len(s) > 1 else 0.0
        out.update({
            "glucose_mean": round(mean, 1),
            "glucose_sd":   round(sd, 1),
            "glucose_cv":   round(sd / mean * 100, 1) if mean else None,
            "tir_pct":      round(float(((s >= TBR_LIMIT) & (s <= TAR_LIMIT)).mean() * 100), 1),
            "tbr_pct":      round(float((s < TBR_LIMIT).mean() * 100), 1),
            "tar_pct":      round(float((s > TAR_LIMIT).mean() * 100), 1),
            # Glucose management indicator (Bergenstal et al., Diabetes Care 2018)
            "gmi_pct":      round(3.31 + 0.02392 * mean, 2),
        })
    return out


# ── Statistics ───────────────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Wilson score interval for a proportion, returned in per cent."""
    if n <= 0:
        return None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - half) * 100, 1), round(min(1.0, centre + half) * 100, 1)


def proportion(k: int, n: int) -> dict[str, Any]:
    lo, hi = wilson_ci(k, n)
    return {
        "k": int(k), "n": int(n),
        "pct": round(k / n * 100, 1) if n else None,
        "ci95": [lo, hi],
    }


def make_histogram(values: list[float], bins: list[float]) -> list[dict]:
    if not values:
        return []
    result = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        count = sum(1 for v in values if lo <= v < hi)
        result.append({"bin": f"{lo}–{hi}", "lo": lo, "hi": hi, "count": count})
    overflow = sum(1 for v in values if v >= bins[-1])
    if overflow:
        result.append({"bin": f"≥{bins[-1]}", "lo": bins[-1], "hi": None, "count": overflow})
    return result


def offset_bin(days: float | None) -> str | None:
    if days is None or (isinstance(days, float) and math.isnan(days)):
        return None
    a = abs(int(days))
    for label, lo, hi in OFFSET_BINS:
        if lo <= a <= hi:
            return label
    return None


def bin_offsets(offsets: Iterable[float | None]) -> dict[str, Any]:
    """Distribution of |offset| over OFFSET_BINS plus signed summary statistics."""
    vals = [float(o) for o in offsets if o is not None and not (isinstance(o, float) and math.isnan(o))]
    n = len(vals)
    bins = []
    for label, _, _ in OFFSET_BINS:
        k = sum(1 for v in vals if offset_bin(v) == label)
        bins.append({"bin": label, **proportion(k, n)})
    s = pd.Series(vals, dtype=float)
    return {
        "n": n,
        "bins": bins,
        "n_before_anchor": int((s < 0).sum()),
        "n_after_anchor": int((s > 0).sum()),
        "median_days": float(s.median()) if n else None,
        "iqr_days": [float(s.quantile(0.25)), float(s.quantile(0.75))] if n else None,
        "min_days": float(s.min()) if n else None,
        "max_days": float(s.max()) if n else None,
    }


def stratified_sample(df: pd.DataFrame, n: int, by: str, seed: int = 42) -> pd.DataFrame:
    """Proportional stratified random sample of n rows (largest-remainder allocation)."""
    if len(df) <= n:
        return df
    sizes = df[by].value_counts()
    raw = sizes / sizes.sum() * n
    alloc = raw.astype(int)
    for key in (raw - alloc).sort_values(ascending=False).index[: n - int(alloc.sum())]:
        alloc[key] += 1
    parts = [
        df[df[by] == key].sample(n=int(k), random_state=seed)
        for key, k in alloc.items() if k > 0
    ]
    return pd.concat(parts).sort_index()


# ── Quality aggregation (shared by live API and offline pipeline) ────────────

def summarise_quality(
    cgm_records: list[dict],
    ecg_records: list[dict],
    *,
    sampling_method: str,
    n_total_cgm: int,
    n_total_ecg: int,
    max_dropout_pct: float = DEFAULT_MAX_CGM_DROPOUT_PCT,
) -> dict[str, Any]:
    """
    cgm_records: dicts with dropout_pct, dropout_nominal_pct, days_covered
    ecg_records: dicts with verdict (one of VERDICTS), hr, qtc
    """
    cgm: dict[str, Any] = {}
    dropouts = [r["dropout_pct"] for r in cgm_records if r.get("dropout_pct") is not None]
    if dropouts:
        nominal = [r["dropout_nominal_pct"] for r in cgm_records if r.get("dropout_nominal_pct") is not None]
        durations = [r["days_covered"] for r in cgm_records if r.get("days_covered") is not None]
        n = len(dropouts)
        under5 = proportion(sum(1 for d in dropouts if d < 5), n)
        under_thr = proportion(sum(1 for d in dropouts if d < max_dropout_pct), n)
        cgm = {
            "n_sampled":               n,
            "n_total":                 n_total_cgm,
            "sampling_method":         sampling_method,
            "mean_dropout_pct":        round(sum(dropouts) / n, 1),
            "median_dropout_pct":      round(float(pd.Series(dropouts).median()), 1),
            "mean_dropout_nominal_pct": round(sum(nominal) / len(nominal), 1) if nominal else None,
            "pct_under5_dropout":      under5["pct"],
            "pct_under5_dropout_ci95": under5["ci95"],
            "dropout_threshold_pct":   max_dropout_pct,
            "pct_under_threshold":     under_thr["pct"],
            "pct_under_threshold_ci95": under_thr["ci95"],
            "mean_duration_days":      round(sum(durations) / len(durations), 1) if durations else None,
            "duration_hist":           make_histogram(durations, [0, 5, 8, 10, 12, 15, 20, 30]),
            "dropout_hist":            make_histogram(dropouts, [0, 2, 5, 10, 20, 50, 100]),
        }

    ecg: dict[str, Any] = {}
    with_verdict = [r for r in ecg_records if r.get("verdict")]
    if with_verdict:
        n = len(with_verdict)
        counts = {v: sum(1 for r in with_verdict if r["verdict"] == v) for v in VERDICTS}
        props = {v: proportion(counts[v], n) for v in VERDICTS}
        hr = [r["hr"] for r in with_verdict if r.get("hr")]
        qtc = [r["qtc"] for r in with_verdict if r.get("qtc")]
        ecg = {
            "n_sampled":            n,
            "n_total":              n_total_ecg,
            "sampling_method":      sampling_method,
            "verdicts":             [
                {"verdict": v, "label": VERDICT_LABELS[v], **props[v]} for v in VERDICTS if counts[v] or v != "unknown"
            ],
            "n_normal":             counts["normal"],
            "n_otherwise_normal":   counts["otherwise_normal"],
            "n_borderline":         counts["borderline"],
            "n_abnormal":           counts["abnormal"],
            "n_unknown":            counts["unknown"],
            "pct_normal":           props["normal"]["pct"],
            "pct_otherwise_normal": props["otherwise_normal"]["pct"],
            "pct_borderline":       props["borderline"]["pct"],
            "pct_abnormal_flag":    props["abnormal"]["pct"],
            "pct_qtc_over_500":     proportion(sum(1 for q in qtc if q > 500), len(qtc))["pct"] if qtc else None,
            "mean_hr":              round(sum(hr) / len(hr), 1) if hr else None,
            "mean_qtc":             round(sum(qtc) / len(qtc), 1) if qtc else None,
            "hr_hist":              make_histogram(hr, [30, 50, 60, 70, 80, 90, 100, 120, 150]),
            "qtc_hist":             make_histogram(qtc, [350, 380, 400, 420, 440, 460, 500]),
        }
    return {"cgm": cgm, "ecg": ecg}


# ── Readiness gates ──────────────────────────────────────────────────────────

GATE_ORDER = ["G0", "G1", "G2", "G3"]
GATE_LABELS = {
    "G0": "Enrolled, ≥1 of ECG / CGM / clinical",
    "G1": "Coverage: ECG + CGM + clinical files",
    "G2": "Integrity: CGM dropout and ECG header",
    "G3": "Temporal: co-registered with the visit",
}


def apply_gates(
    df: pd.DataFrame,
    *,
    tau_days: int = DEFAULT_TAU_DAYS,
    max_dropout_pct: float = DEFAULT_MAX_CGM_DROPOUT_PCT,
    ecg_temporal: bool = False,
) -> dict[str, pd.Series]:
    """
    Cumulative readiness gates over a participant readiness table (one row per
    participant; see scripts/build_readiness_table.py for the columns).

    G0  at least one of ECG, CGM or clinical data present
    G1  G0 + ECG, CGM and clinical files all present           (coverage)
    G2  G1 + CGM dropout < max_dropout_pct and ECG readable     (integrity)
    G3  G2 + |CGM start − visit| ≤ tau_days                     (temporal)
          and, if ecg_temporal, |ECG date − visit| ≤ tau_days
    """
    def col(name: str, default: Any = False) -> pd.Series:
        return df[name] if name in df.columns else pd.Series(default, index=df.index)

    has_ecg = col("has_ecg_file").fillna(False).astype(bool)
    has_cgm = col("has_cgm_file").fillna(False).astype(bool)
    has_clin = col("has_clinical").fillna(False).astype(bool)

    g0 = has_ecg | has_cgm | has_clin
    g1 = g0 & has_ecg & has_cgm & has_clin
    dropout = pd.to_numeric(col("cgm_dropout_pct", None), errors="coerce")
    g2 = g1 & (dropout < max_dropout_pct) & col("ecg_header_ok").fillna(False).astype(bool)
    cgm_off = pd.to_numeric(col("cgm_offset_days", None), errors="coerce")
    g3 = g2 & (cgm_off.abs() <= tau_days)
    if ecg_temporal:
        ecg_off = pd.to_numeric(col("ecg_offset_days", None), errors="coerce")
        g3 = g3 & (ecg_off.abs() <= tau_days)
    return {"G0": g0, "G1": g1, "G2": g2, "G3": g3}


def gate_funnel(df: pd.DataFrame, gates: dict[str, pd.Series], group_col: str = "study_group") -> list[dict]:
    """Participants retained at each gate, overall and per group."""
    rows = []
    base = int(gates["G0"].sum())
    groups = sorted(df[group_col].dropna().unique()) if group_col in df.columns else []
    for g in GATE_ORDER:
        mask = gates[g]
        row = {
            "gate": g,
            "label": GATE_LABELS[g],
            "n": int(mask.sum()),
            "pct_of_G0": round(mask.sum() / base * 100, 1) if base else None,
            "by_group": {},
        }
        for grp in groups:
            in_grp = df[group_col] == grp
            g0_grp = int((gates["G0"] & in_grp).sum())
            k = int((mask & in_grp).sum())
            row["by_group"][grp] = {"n": k, "pct_of_G0": round(k / g0_grp * 100, 1) if g0_grp else None}
        rows.append(row)
    return rows


# ── validation_date interpretation (heuristic, to be confirmed manually) ─────

def interpret_validation_date(
    ecg_visit_bins: dict[str, Any],
    n_distinct_dates: int,
    n_dates: int,
    tau_days: int = DEFAULT_TAU_DAYS,
) -> dict[str, Any]:
    """
    Heuristic reading of what `validation_date` measures.

    If most ECG dates fall within tau of the clinical visit, the field behaves
    like an acquisition date. If few do, and many records share a small set of
    dates, it behaves like a batch processing/export date. The output is a
    prompt for manual confirmation, never a substitute for it.
    """
    within = sum(b["k"] for b in ecg_visit_bins.get("bins", []) if b["bin"] in ("same day", "1–7 d"))
    n = ecg_visit_bins.get("n", 0) or 0
    frac_within = within / n if n else 0.0
    distinct_ratio = n_distinct_dates / n_dates if n_dates else 0.0
    if n == 0:
        verdict = "insufficient_data"
    elif frac_within >= 0.8:
        verdict = "behaves_like_acquisition_date"
    elif frac_within < 0.2 and distinct_ratio < 0.05:
        verdict = "behaves_like_processing_date"
    else:
        verdict = "ambiguous"
    return {
        "verdict": verdict,
        "fraction_within_tau_of_visit": round(frac_within, 3),
        "tau_days": tau_days,
        "distinct_date_ratio": round(distinct_ratio, 4),
        "note": "Heuristic only. Confirm with the manual verification sample and the AI-READI ECG documentation.",
    }

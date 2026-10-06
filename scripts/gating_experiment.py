#!/usr/bin/env python3
"""
gating_experiment.py — step 4 of the evidence pipeline.

Question: does applying the three readiness gates (coverage → integrity →
temporal co-registration) change how well an ECG + CGM + clinical model
diagnoses type 2 diabetes, and which participants does gating remove?

Hypotheses (fixed before running; see docs/EXPERIMENT_PREREGISTRATION.md):
  H1  Training on the gated cohort (G3) gives a higher AUROC on the common
      clean test set than training on the ungated cohort (G0).
  H2  Any G3 gain exceeds what a random subsample of G0 of the same size
      achieves (G3-rand), i.e. it is not explained by sample size alone.
  H3  Gating removes participants unevenly across study groups.

Design
  task (primary)    T2D (oral-medication + insulin groups) vs no T2D
                    (healthy + pre-DM); AUROC and AUPRC
  task (secondary)  HbA1c regression; MAE
  features          ECG header intervals + Philips verdict; CGM summary
                    (mean, SD, CV, TIR, TBR, TAR, GMI); clinical (age, sex,
                    BMI, BP, lipids). HbA1c, glucose and medications are
                    EXCLUDED from the diagnosis features (they define groups).
  split             AI-READI recommended train / val / test
  models            logistic regression (median imputation + missing
                    indicators + scaling) and histogram gradient boosting;
                    hyperparameters chosen on the val split
  evaluation        every condition on ONE common test set (test ∩ G3),
                    plus the full test set; 95% CIs from 1,000 bootstrap
                    resamples; paired bootstrap for G3 − G0
  controls          G3-rand: 20 random subsamples of G0-train of |G3-train|
  ablation          modality subsets under G3

Outputs
  results/gating_results.json

Usage
  python scripts/gating_experiment.py [--tau 7] [--max-dropout 10]
        [--ecg-temporal auto|require|ignore] [--bootstrap 1000] [--rand-repeats 20]
"""

from __future__ import annotations

import argparse
import time
import warnings

import numpy as np
import pandas as pd

from _common import banner, load_readiness_table, provenance, read_json, write_json

T2D_GROUPS = {
    "oral_medication_and_or_non_insulin_injectable_medication_controlled",
    "insulin_dependent",
}
VERDICT_CATS = ["normal", "otherwise_normal", "borderline", "abnormal"]

ECG_FEATURES = ["ecg_hr", "ecg_pr", "ecg_qrsd", "ecg_qt", "ecg_qtc"] + [f"ecg_v_{v}" for v in VERDICT_CATS]
CGM_FEATURES = ["cgm_mean", "cgm_sd", "cgm_cv", "cgm_tir", "cgm_tbr", "cgm_tar", "cgm_gmi"]
CLINICAL_FEATURES = ["age", "sex_male", "bmi", "sbp", "dbp", "chol_total", "hdl", "ldl", "tg"]
MODALITIES = {"ECG": ECG_FEATURES, "CGM": CGM_FEATURES, "Clinical": CLINICAL_FEATURES}

OMOP_FEATURES = {  # concept_id → column
    4245997: "bmi", 3004249: "sbp", 3012888: "dbp", 3027114: "chol_total",
    3007070: "hdl", 3028288: "ldl", 3022192: "tg", 3004410: "hba1c",
}

HYPOTHESES = {
    "H1": "AUROC(train G3) > AUROC(train G0) on the common clean test set (test ∩ G3).",
    "H2": "AUROC(train G3) exceeds the G3-rand distribution (random G0 subsamples of equal size).",
    "H3": "Gating removes participants unevenly across study groups.",
}


# ── Features ─────────────────────────────────────────────────────────────────

def omop_features() -> pd.DataFrame:
    """Per-person median of each OMOP feature after unit validation and range filtering."""
    from services.omop_service import (
        CONCEPT_META, PLAUSIBLE_RANGES, UNIT_CONVERSIONS, _load_measurement, _load_person,
    )

    meas = _load_measurement()
    meas = meas[meas["measurement_concept_id"].isin(list(OMOP_FEATURES))].copy()
    meas = meas.dropna(subset=["value_as_number"])
    unit = meas["unit_source_value"].fillna("").astype(str).str.strip()
    canonical = meas["measurement_concept_id"].map(lambda c: CONCEPT_META[c]["unit"])
    factor = pd.Series(np.nan, index=meas.index)
    factor[(unit == "") | (unit == canonical)] = 1.0
    for (obs, canon), mult in UNIT_CONVERSIONS.items():
        factor[(unit == obs) & (canonical == canon)] = mult
    meas["value"] = meas["value_as_number"].astype(float) * factor
    meas = meas.dropna(subset=["value"])
    lo = meas["measurement_concept_id"].map(lambda c: PLAUSIBLE_RANGES.get(c, (-np.inf, np.inf))[0])
    hi = meas["measurement_concept_id"].map(lambda c: PLAUSIBLE_RANGES.get(c, (-np.inf, np.inf))[1])
    meas = meas[(meas["value"] >= lo) & (meas["value"] <= hi)]
    wide = (meas.groupby(["person_id", "measurement_concept_id"])["value"].median()
                .unstack().rename(columns=OMOP_FEATURES))
    wide.index = wide.index.astype(str)

    try:
        person = _load_person()
        sex = (person.set_index("person_id")["gender_concept_id"] == 8507).astype(float)
        wide = wide.join(sex.rename("sex_male"), how="outer")
    except (OSError, KeyError):
        wide["sex_male"] = np.nan
    for col in list(OMOP_FEATURES.values()) + ["sex_male"]:
        if col not in wide.columns:
            wide[col] = np.nan
    return wide


def build_dataset(table: pd.DataFrame) -> pd.DataFrame:
    df = table.copy()
    df = df.join(omop_features(), on="person_id")
    for v in VERDICT_CATS:
        df[f"ecg_v_{v}"] = np.where(df["ecg_verdict"].isna(), np.nan, (df["ecg_verdict"] == v).astype(float))
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["label_t2d"] = df["study_group"].isin(T2D_GROUPS).astype(int)
    return df


# ── Models ───────────────────────────────────────────────────────────────────

def make_classifier(kind: str, params: dict, seed: int):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if kind == "logreg":
        return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                             LogisticRegression(C=params.get("C", 1.0), max_iter=5000))
    return HistGradientBoostingClassifier(learning_rate=params.get("learning_rate", 0.1),
                                          max_depth=params.get("max_depth", 3),
                                          max_iter=params.get("max_iter", 200), random_state=seed)


def make_regressor(kind: str, params: dict, seed: int):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if kind == "logreg":  # linear counterpart for regression
        return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                             Ridge(alpha=params.get("alpha", 1.0)))
    return HistGradientBoostingRegressor(learning_rate=params.get("learning_rate", 0.1),
                                         max_depth=params.get("max_depth", 3),
                                         max_iter=params.get("max_iter", 200), random_state=seed)


GRIDS = {
    "classification": {
        "logreg": [{"C": c} for c in (0.01, 0.1, 1.0, 10.0)],
        "hgb": [{"learning_rate": lr, "max_depth": d} for lr in (0.05, 0.1) for d in (2, 3, None)],
    },
    "regression": {
        "logreg": [{"alpha": a} for a in (0.1, 1.0, 10.0, 100.0)],
        "hgb": [{"learning_rate": lr, "max_depth": d} for lr in (0.05, 0.1) for d in (2, 3, None)],
    },
}


def _auroc(y, p):
    from sklearn.metrics import roc_auc_score
    return roc_auc_score(y, p) if len(np.unique(y)) == 2 else np.nan


def _auprc(y, p):
    from sklearn.metrics import average_precision_score
    return average_precision_score(y, p) if len(np.unique(y)) == 2 else np.nan


def _mae(y, p):
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p)))) if len(y) else np.nan


def select_params(task, kind, X_tr, y_tr, X_val, y_val, seed):
    grid = GRIDS[task][kind]
    if len(X_val) < 10 or (task == "classification" and len(np.unique(y_val)) < 2):
        return grid[len(grid) // 2], None
    best, best_score = None, None
    for params in grid:
        if task == "classification":
            m = make_classifier(kind, params, seed).fit(X_tr, y_tr)
            score = _auroc(y_val, m.predict_proba(X_val)[:, 1])
        else:
            m = make_regressor(kind, params, seed).fit(X_tr, y_tr)
            score = -_mae(y_val, m.predict(X_val))
        if best_score is None or (not np.isnan(score) and score > best_score):
            best, best_score = params, score
    return best, best_score


def bootstrap(metric, y, p, idx_sets):
    vals = np.array([metric(y[i], p[i]) for i in idx_sets], dtype=float)
    vals = vals[~np.isnan(vals)]
    if not len(vals):
        return [None, None]
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)]


def evaluate(task, y, p, idx_sets):
    if task == "classification":
        return {
            "n": int(len(y)), "n_pos": int(np.sum(y)),
            "auroc": round(float(_auroc(y, p)), 4) if len(y) else None,
            "auroc_ci95": bootstrap(_auroc, y, p, idx_sets),
            "auprc": round(float(_auprc(y, p)), 4) if len(y) else None,
            "auprc_ci95": bootstrap(_auprc, y, p, idx_sets),
        }
    return {"n": int(len(y)), "mae": round(_mae(y, p), 4), "mae_ci95": bootstrap(_mae, y, p, idx_sets)}


def clean(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else v


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tau", type=int, default=7)
    ap.add_argument("--max-dropout", type=float, default=10.0)
    ap.add_argument("--ecg-temporal", choices=["auto", "require", "ignore"], default="auto")
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--rand-repeats", type=int, default=20)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    warnings.filterwarnings("ignore", category=UserWarning)

    from services.readiness_service import apply_gates, gate_funnel

    banner("Readiness gating experiment")
    t_start = time.perf_counter()
    rng = np.random.default_rng(args.seed)

    df = build_dataset(load_readiness_table())

    audit = read_json("ecg_date_audit.json")
    if args.ecg_temporal == "auto":
        verdict = (audit or {}).get("validation_date_interpretation", {}).get("verdict")
        ecg_temporal = verdict == "behaves_like_acquisition_date"
    else:
        ecg_temporal = args.ecg_temporal == "require"
    gates = apply_gates(df, tau_days=args.tau, max_dropout_pct=args.max_dropout, ecg_temporal=ecg_temporal)

    split = df["recommended_split"].astype(str)
    features_all = ECG_FEATURES + CGM_FEATURES + CLINICAL_FEATURES

    tasks = {
        "diagnosis_t2d": ("classification", "label_t2d", df["label_t2d"].notna()),
        "hba1c_regression": ("regression", "hba1c", df["hba1c"].notna()),
    }

    results: dict = {"tasks": {}}
    for task_name, (task, target, has_target) in tasks.items():
        test_clean = (split == "test") & gates["G3"] & has_target
        test_all = (split == "test") & gates["G0"] & has_target
        eval_sets = {"test_clean": test_clean, "test_all": test_all}
        boot_idx = {
            k: [rng.integers(0, int(m.sum()), int(m.sum())) for _ in range(args.bootstrap)] if m.sum() else []
            for k, m in eval_sets.items()
        }
        task_out: dict = {"type": task, "target": target, "eval_sets": {k: int(m.sum()) for k, m in eval_sets.items()},
                          "conditions": {}, "g3_rand": {}, "paired_g3_minus_g0": {}, "ablation_g3": {}}

        def fit_predict(kind, train_mask, feats, seed=args.seed):
            tr = (split == "train") & train_mask & has_target
            va = (split == "val") & train_mask & has_target
            X_tr, y_tr = df.loc[tr, feats], df.loc[tr, target].to_numpy()
            if len(X_tr) < 10 or (task == "classification" and len(np.unique(y_tr)) < 2):
                return None, int(tr.sum()), None
            params, _ = select_params(task, kind, X_tr, y_tr, df.loc[va, feats], df.loc[va, target].to_numpy(), seed)
            model = (make_classifier if task == "classification" else make_regressor)(kind, params, seed)
            model.fit(X_tr, y_tr)
            preds = {}
            for k, m in eval_sets.items():
                if m.sum():
                    X = df.loc[m, feats]
                    preds[k] = model.predict_proba(X)[:, 1] if task == "classification" else model.predict(X)
            return preds, int(tr.sum()), params

        for kind in ("logreg", "hgb"):
            cond_out, cond_preds = {}, {}
            for g in ("G0", "G1", "G2", "G3"):
                preds, n_train, params = fit_predict(kind, gates[g], features_all)
                entry = {"n_train": n_train, "params": params}
                if preds:
                    cond_preds[g] = preds
                    for k, p in preds.items():
                        y = df.loc[eval_sets[k], target].to_numpy()
                        entry[k] = evaluate(task, y, p, boot_idx[k])
                cond_out[g] = entry
            task_out["conditions"][kind] = cond_out

            # Paired bootstrap: G3 − G0 on the common clean test set
            if "G3" in cond_preds and "G0" in cond_preds and "test_clean" in cond_preds["G3"]:
                y = df.loc[test_clean, target].to_numpy()
                metric = _auroc if task == "classification" else _mae
                p3, p0 = cond_preds["G3"]["test_clean"], cond_preds["G0"]["test_clean"]
                diffs = np.array([metric(y[i], p3[i]) - metric(y[i], p0[i]) for i in boot_idx["test_clean"]])
                diffs = diffs[~np.isnan(diffs)]
                if len(diffs):
                    point = metric(y, p3) - metric(y, p0)
                    task_out["paired_g3_minus_g0"][kind] = {
                        "metric": "auroc" if task == "classification" else "mae",
                        "difference": round(float(point), 4),
                        "ci95": [round(float(np.percentile(diffs, 2.5)), 4), round(float(np.percentile(diffs, 97.5)), 4)],
                        "share_of_resamples_g3_better": round(float(np.mean(diffs > 0 if task == "classification" else diffs < 0)), 3),
                    }

            # G3-rand control: random G0 subsets with the size of G3's training set
            n_g3_train = int(((split == "train") & gates["G3"] & has_target).sum())
            g0_train_idx = df.index[(split == "train") & gates["G0"] & has_target]
            scores = []
            for r in range(args.rand_repeats):
                if n_g3_train < 10 or n_g3_train > len(g0_train_idx):
                    break
                chosen = rng.choice(g0_train_idx, size=n_g3_train, replace=False)
                mask = pd.Series(False, index=df.index)
                mask.loc[chosen] = True
                mask |= (split == "val") & gates["G0"]   # validation stays the ungated val split
                preds, _, _ = fit_predict(kind, mask, features_all, seed=args.seed + r)
                if preds and "test_clean" in preds:
                    y = df.loc[test_clean, target].to_numpy()
                    scores.append(_auroc(y, preds["test_clean"]) if task == "classification"
                                  else _mae(y, preds["test_clean"]))
            scores = [s for s in scores if not np.isnan(s)]
            g3_entry = cond_out.get("G3", {}).get("test_clean", {})
            g3_score = g3_entry.get("auroc" if task == "classification" else "mae")
            task_out["g3_rand"][kind] = {
                "repeats": len(scores), "n_train": n_g3_train,
                "mean": round(float(np.mean(scores)), 4) if scores else None,
                "sd": round(float(np.std(scores, ddof=1)), 4) if len(scores) > 1 else None,
                "share_at_least_as_good_as_g3": (
                    round(float(np.mean([s >= g3_score if task == "classification" else s <= g3_score
                                         for s in scores])), 3) if scores and g3_score is not None else None),
            }

            # Modality ablation under G3
            ablation = {}
            for name, feats in {
                "ECG": ECG_FEATURES, "CGM": CGM_FEATURES, "Clinical": CLINICAL_FEATURES,
                "ECG+CGM": ECG_FEATURES + CGM_FEATURES, "ECG+Clinical": ECG_FEATURES + CLINICAL_FEATURES,
                "CGM+Clinical": CGM_FEATURES + CLINICAL_FEATURES, "All": features_all,
            }.items():
                preds, n_train, _ = fit_predict(kind, gates["G3"], feats)
                if preds and "test_clean" in preds:
                    y = df.loc[test_clean, target].to_numpy()
                    ablation[name] = evaluate(task, y, preds["test_clean"], boot_idx["test_clean"])
            task_out["ablation_g3"][kind] = ablation

        results["tasks"][task_name] = task_out

    # H3: attrition by study group, and class balance in the training split
    train = split == "train"
    results["attrition"] = {
        "funnel_all_splits": gate_funnel(df, gates),
        "train_t2d_prevalence": {
            g: round(float(df.loc[train & gates[g], "label_t2d"].mean()) * 100, 1) if (train & gates[g]).any() else None
            for g in ("G0", "G1", "G2", "G3")
        },
    }
    g0_by_group = df[gates["G0"]].groupby("study_group").size()
    g3_by_group = df[gates["G3"]].groupby("study_group").size()
    retained = (g3_by_group / g0_by_group).fillna(0)
    if len(retained) > 1:
        from scipy.stats import chi2_contingency
        table = np.array([g3_by_group.reindex(g0_by_group.index, fill_value=0).to_numpy(),
                          (g0_by_group - g3_by_group.reindex(g0_by_group.index, fill_value=0)).to_numpy()])
        try:
            chi2, p, dof, _ = chi2_contingency(table)
        except ValueError:  # a zero row/column makes the test undefined
            chi2, p, dof = None, None, None
        results["attrition"]["retention_by_group_pct"] = {k: round(float(v) * 100, 1) for k, v in retained.items()}
        results["attrition"]["retention_chi2"] = {"chi2": clean(chi2), "dof": dof, "p_value": clean(p)}

    results["hypotheses"] = HYPOTHESES
    results["features"] = {"ECG": ECG_FEATURES, "CGM": CGM_FEATURES, "Clinical": CLINICAL_FEATURES,
                           "excluded_for_diagnosis": ["hba1c", "glucose", "insulin", "c-peptide", "medications"]}
    results["gate_params"] = {"tau_days": args.tau, "max_cgm_dropout_pct": args.max_dropout, "ecg_temporal": ecg_temporal}
    results["elapsed_seconds"] = round(time.perf_counter() - t_start, 1)
    results["_meta"] = provenance("gating_experiment.py", **vars(args))
    write_json("gating_results.json", results)

    # Console summary
    for task_name, t in results["tasks"].items():
        metric = "auroc" if t["type"] == "classification" else "mae"
        print(f"\n{task_name}  (test_clean n={t['eval_sets']['test_clean']}, test_all n={t['eval_sets']['test_all']})")
        for kind, conds in t["conditions"].items():
            line = "  ".join(
                f"{g}: {c.get('test_clean', {}).get(metric)} (n_train {c['n_train']})" for g, c in conds.items())
            print(f"  {kind:<7} {line}")
            if kind in t["paired_g3_minus_g0"]:
                d = t["paired_g3_minus_g0"][kind]
                print(f"          G3−G0 {d['metric']}: {d['difference']} CI {d['ci95']}")
            gr = t["g3_rand"].get(kind, {})
            print(f"          G3-rand mean {gr.get('mean')} ± {gr.get('sd')}  (share ≥ G3: {gr.get('share_at_least_as_good_as_g3')})")
    print(f"\nRetention by group (G3/G0): {results['attrition'].get('retention_by_group_pct')}")
    print(f"Elapsed {results['elapsed_seconds']} s — wrote results/gating_results.json")


if __name__ == "__main__":
    main()

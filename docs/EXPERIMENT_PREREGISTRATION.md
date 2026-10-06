# Readiness-gating experiment — analysis plan (fixed before running)

Written before `scripts/gating_experiment.py` is run on AI-READI v3.0.0. Any later
change to this plan is listed under *Deviations* with its reason.

## Question
Does applying the three readiness gates change how well a multimodal model
diagnoses type 2 diabetes, and which participants does gating remove?

## Hypotheses
- **H1** Training on the gated cohort (G3) gives a higher AUROC on the common clean
  test set than training on the ungated cohort (G0).
- **H2** Any G3 gain exceeds what random subsamples of G0 of the same size achieve
  (G3-rand), so it is not explained by sample size alone.
- **H3** Gating removes participants unevenly across study groups (χ² test on
  retained vs removed by group).

A null result for H1/H2 is reported as such. "Coverage and integrity are not the
bottleneck in AI-READI" is an acceptable conclusion.

## Gates (cumulative)
| Gate | Rule |
| --- | --- |
| G0 | at least one of ECG, CGM or clinical data present |
| G1 | ECG + CGM + clinical files all present (coverage) |
| G2 | G1 + CGM dropout < 10 % (observed span) + ECG header readable (integrity) |
| G3 | G2 + \|CGM start − visit\| ≤ τ = 7 days; the ECG date enters this gate only if the date audit shows `validation_date` behaves like an acquisition date (temporal) |

## Tasks, features, models
- **Primary:** T2D (oral-medication + insulin groups) vs no T2D (healthy + pre-DM); AUROC, AUPRC.
- **Secondary:** HbA1c regression; MAE.
- **Features:** ECG header intervals (HR, PR, QRS, QT, QTc) and Philips verdict;
  CGM mean, SD, CV, TIR, TBR, TAR, GMI; age, sex, BMI, SBP, DBP, lipids.
  HbA1c, glucose, insulin, C-peptide and medications are excluded from the
  diagnosis features because they define the study groups.
- **Models:** logistic regression (median imputation + missing indicators +
  scaling) and histogram gradient boosting. Hyperparameters from a fixed grid,
  chosen on the AI-READI `val` split.
- **Split:** AI-READI `recommended_split`. No participant appears in two splits.

## Evaluation
- Every condition is evaluated on one common clean test set (test ∩ G3) and on the
  full test set (test ∩ G0).
- 95 % CIs from 1,000 bootstrap resamples of the test set; G3 − G0 by paired bootstrap.
- G3-rand: 20 random subsamples of G0-train with |G3-train| participants.
- Modality ablation under G3.

## Deviations
_None yet._

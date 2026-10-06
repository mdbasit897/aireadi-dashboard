"""
Final ECG classification audit.
Uses interpretation_comment_2 as the authoritative Philips verdict field.

Run from backend directory:
    DATASET_ROOT=$(grep DATASET_ROOT ../.env | cut -d'=' -f2) python3 ecg_final_audit.py
"""
import sys
sys.path.insert(0, '.')
from services.eda_service import _find_ecg_record
from services.cohort_service import load_participants
import wfdb
from collections import Counter

participants = load_participants()
ecg_pids = participants[participants["cardiac_ecg"] == True]["person_id"].astype(str).tolist()[:150]

verdict_counts = Counter()
secondary_flags = Counter()   # comment_N_key findings in ABNORMAL ECGs
normal_with_secondary = 0     # OTHERWISE NORMAL ECGs that have a secondary comment

results = []

for pid in ecg_pids:
    rec = _find_ecg_record(pid)
    if not rec:
        continue
    try:
        header = wfdb.rdheader(rec)
        comments = header.comments or []
        meta = {}
        for c in comments:
            if ":" in c:
                k, _, v = c.partition(":")
                meta[k.strip()] = v.strip()

        interp_2 = meta.get("interpretation_comment_2", "").strip()
        verdict   = interp_2  # e.g. "- ABNORMAL ECG -", "- NORMAL ECG -", "- OTHERWISE NORMAL ECG -"
        verdict_counts[verdict] += 1

        # Collect secondary comment keys for ABNORMAL ECGs
        if "ABNORMAL ECG" in interp_2.upper():
            for i in range(1, 6):
                ck = meta.get(f"comment_{i}_key", "").strip()
                if ck:
                    secondary_flags[ck] += 1

        # Count OTHERWISE NORMAL ECGs that have a secondary annotation
        if "OTHERWISE NORMAL" in interp_2.upper():
            has_secondary = any(
                meta.get(f"comment_{i}_key", "").strip()
                for i in range(2, 6)  # comment_1 is always sinus rhythm
            )
            if has_secondary:
                normal_with_secondary += 1

        results.append({"pid": pid, "verdict": verdict})

    except Exception:
        continue

total = len(results)
print(f"Total ECGs parsed: {total}")
print()

print("=== PHILIPS MACHINE VERDICT DISTRIBUTION (interpretation_comment_2) ===")
for verdict, count in verdict_counts.most_common():
    pct = round(count / total * 100, 1)
    print(f"  {verdict:<35} {count:>4}  ({pct}%)")

print()
n_abnormal        = sum(v for k, v in verdict_counts.items() if "ABNORMAL ECG" in k.upper() and "OTHERWISE" not in k.upper())
n_otherwise_normal = sum(v for k, v in verdict_counts.items() if "OTHERWISE NORMAL" in k.upper())
n_normal          = sum(v for k, v in verdict_counts.items() if k.strip() == "- NORMAL ECG -")

print(f"Summary:")
print(f"  Strict ABNORMAL ECG:          {n_abnormal}/{total} = {round(n_abnormal/total*100,1)}%")
print(f"  OTHERWISE NORMAL (minor find):{n_otherwise_normal}/{total} = {round(n_otherwise_normal/total*100,1)}%")
print(f"    of which have a secondary annotation: {normal_with_secondary}")
print(f"  NORMAL ECG:                   {n_normal}/{total} = {round(n_normal/total*100,1)}%")
print(f"  ABNORMAL + OTHERWISE NORMAL:  {n_abnormal+n_otherwise_normal}/{total} = {round((n_abnormal+n_otherwise_normal)/total*100,1)}%")

print()
print("=== SECONDARY FINDINGS IN STRICT ABNORMAL ECGs (comment_N_key) ===")
for finding, count in secondary_flags.most_common(15):
    print(f"  {finding:<50} {count:>4}")

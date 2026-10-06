"""
Run this on the VM to see the actual interpretation comment content
for both flagged and normal ECGs.

Usage:
    DATASET_ROOT=$(grep DATASET_ROOT ../.env | cut -d'=' -f2) python3 ecg_interp_audit.py
"""
import sys
sys.path.insert(0, '.')
from services.eda_service import _find_ecg_record
from services.cohort_service import load_participants
import wfdb

INTERP_FIELDS = [
    "interpretation_comment_1", "interpretation_comment_2",
    "comment_1_key", "comment_1_val",
    "comment_2_key", "comment_2_val",
    "comment_3_key", "comment_3_val",
    "comment_4_key", "comment_4_val",
    "machine_text",
]

ABNORMAL_KEYWORDS = [
    "ST elevation", "ST depression", "atrial fibrillation",
    "left bundle", "right bundle", "ischemia", "infarct",
    "bradycardia", "tachycardia", "abnormal ecg",
    "abnormal rhythm", "abnormal axis",
]

participants = load_participants()
ecg_pids = participants[participants["cardiac_ecg"] == True]["person_id"].astype(str).tolist()[:150]

flagged   = []
normal    = []
all_interp_texts = []

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

        interp_text = " ".join(str(meta.get(f, "")) for f in INTERP_FIELDS).lower().strip()
        matched_kws = [kw for kw in ABNORMAL_KEYWORDS if kw.lower() in interp_text]
        is_flagged  = bool(matched_kws)

        entry = {
            "pid":           pid,
            "interp_text":   interp_text,
            "matched_kws":   matched_kws,
            "comment_1_key": meta.get("comment_1_key", ""),
            "comment_1_val": meta.get("comment_1_val", ""),
            "comment_2_key": meta.get("comment_2_key", ""),
            "comment_2_val": meta.get("comment_2_val", ""),
            "interp_1":      meta.get("interpretation_comment_1", ""),
            "interp_2":      meta.get("interpretation_comment_2", ""),
            "machine_text":  meta.get("machine_text", ""),
        }
        all_interp_texts.append(interp_text)

        if is_flagged:
            flagged.append(entry)
        else:
            normal.append(entry)
    except Exception as e:
        pass

print(f"Total parsed: {len(flagged)+len(normal)}  |  Flagged: {len(flagged)}  |  Normal: {len(normal)}")
print(f"Flagged rate: {round(len(flagged)/(len(flagged)+len(normal))*100,1)}%")

print("\n" + "="*70)
print("FIRST 5 FLAGGED — full interpretation fields")
print("="*70)
for ex in flagged[:5]:
    print(f"\n--- PID {ex['pid']} ---")
    print(f"  interp_1:      {ex['interp_1']!r}")
    print(f"  interp_2:      {ex['interp_2']!r}")
    print(f"  comment_1_key: {ex['comment_1_key']!r}  val: {ex['comment_1_val']!r}")
    print(f"  comment_2_key: {ex['comment_2_key']!r}  val: {ex['comment_2_val']!r}")
    print(f"  machine_text:  {ex['machine_text']!r}")
    print(f"  matched_kws:   {ex['matched_kws']}")

print("\n" + "="*70)
print("FIRST 5 NORMAL — full interpretation fields (for comparison)")
print("="*70)
for ex in normal[:5]:
    print(f"\n--- PID {ex['pid']} ---")
    print(f"  interp_1:      {ex['interp_1']!r}")
    print(f"  interp_2:      {ex['interp_2']!r}")
    print(f"  comment_1_key: {ex['comment_1_key']!r}  val: {ex['comment_1_val']!r}")
    print(f"  comment_2_key: {ex['comment_2_key']!r}  val: {ex['comment_2_val']!r}")
    print(f"  machine_text:  {ex['machine_text']!r}")

print("\n" + "="*70)
print("KEYWORD FREQUENCY across all flagged ECGs")
print("="*70)
from collections import Counter
kw_counts = Counter()
for ex in flagged:
    for kw in ex['matched_kws']:
        kw_counts[kw] += 1
for kw, count in kw_counts.most_common():
    print(f"  {kw:<30} {count:>4}  ({round(count/len(flagged)*100,1)}% of flagged)")

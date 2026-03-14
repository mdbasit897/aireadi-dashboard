#!/usr/bin/env python3
"""
preprocess.py — One-time dataset indexing script.

Run this once after setting DATASET_ROOT in your .env file.
It scans the dataset directory and writes data/participants_index.json,
which is used by the backend to quickly resolve file paths.

Usage:
    cd scripts
    python preprocess.py
"""
import os
import sys
import json
import glob
import csv
from pathlib import Path

# Allow importing from backend
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from config import get_settings

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "participants_index.json"


def scan_ecg(ecg_dir: str, person_ids: list[str]) -> dict[str, str | None]:
    index = {}
    for pid in person_ids:
        pattern1 = os.path.join(ecg_dir, pid, "*.hea")
        pattern2 = os.path.join(ecg_dir, f"{pid}*.hea")
        matches = glob.glob(pattern1) or glob.glob(pattern2)
        index[pid] = matches[0].replace(".hea", "") if matches else None
    return index


def scan_cgm(cgm_dir: str, person_ids: list[str]) -> dict[str, list[str]]:
    index = {}
    for pid in person_ids:
        pattern = os.path.join(cgm_dir, pid, "**", "*.json")
        files = glob.glob(pattern, recursive=True)
        if not files:
            files = glob.glob(os.path.join(cgm_dir, f"{pid}*.json"))
        index[pid] = files
    return index


def main():
    settings = get_settings()
    print(f"Dataset root: {settings.dataset_root}")

    if not os.path.exists(settings.participants_tsv):
        print(f"ERROR: participants.tsv not found at {settings.participants_tsv}")
        sys.exit(1)

    # Load participant IDs
    with open(settings.participants_tsv) as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
    person_ids = [r["person_id"] for r in rows]
    print(f"Found {len(person_ids)} participants")

    print("Scanning ECG files...")
    ecg_index = scan_ecg(settings.ecg_dir, person_ids)
    ecg_found = sum(1 for v in ecg_index.values() if v)
    print(f"  ECG records found: {ecg_found}/{len(person_ids)}")

    print("Scanning CGM files...")
    cgm_index = scan_cgm(settings.cgm_dir, person_ids)
    cgm_found = sum(1 for v in cgm_index.values() if v)
    print(f"  CGM files found for: {cgm_found}/{len(person_ids)} participants")

    index = {
        "ecg": ecg_index,
        "cgm": cgm_index,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(index, f, indent=2)

    print(f"\nIndex written to {OUTPUT_PATH}")
    print("You can now start the backend with: uvicorn main:app --reload")


if __name__ == "__main__":
    main()

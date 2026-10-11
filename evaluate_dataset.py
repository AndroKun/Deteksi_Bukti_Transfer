"""Evaluasi hasil berlabel; hasil tidak meyakinkan dilaporkan terpisah."""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path


PREDICTION_MAP = {
    "indikasi_manipulasi": "manipulasi",
    "tidak_ditemukan_indikasi": "asli",
    "tidak_meyakinkan": None,
}


def evaluate_rows(rows):
    labels = {"asli", "manipulasi"}
    counts = {"tn": 0, "fp": 0, "fn": 0, "tp": 0}
    excluded = 0
    total = 0
    for row in rows:
        actual = row.get("label_aktual", "").strip()
        predicted = PREDICTION_MAP.get(row.get("hasil_prediksi", "").strip())
        if actual not in labels:
            raise ValueError(f"label_aktual tidak valid: {actual!r}")
        total += 1
        if predicted is None:
            excluded += 1
        elif predicted == "manipulasi" and actual == "manipulasi":
            counts["tp"] += 1
        elif predicted == "manipulasi":
            counts["fp"] += 1
        elif actual == "manipulasi":
            counts["fn"] += 1
        else:
            counts["tn"] += 1

    evaluated = total - excluded
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    precision = tp / (tp + fp) if evaluated and tp + fp else None
    recall = tp / (tp + fn) if evaluated and tp + fn else None
    if not evaluated:
        f1 = None
    elif precision is not None and recall is not None and precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    return {
        "confusion_matrix": {"actual_asli": {"prediksi_asli": tn, "prediksi_manipulasi": fp},
                             "actual_manipulasi": {"prediksi_asli": fn, "prediksi_manipulasi": tp}},
        "jumlah_total": total,
        "prediksi_inkonklusif_dikecualikan": excluded,
        "coverage": evaluated / total if total else 0.0,
        "accuracy": (tp + tn) / evaluated if evaluated else None,
        "precision_manipulasi": precision,
        "recall_manipulasi": recall,
        "f1_manipulasi": f1,
        "catatan": "Metrik hanya deskriptif untuk label dan prediksi yang diberikan; bukan validasi metode.",
    }


def read_records(path):
    if path.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                "SELECT true_label, result_json FROM checks WHERE true_label IS NOT NULL"
            ).fetchall()
        return [
            {"label_aktual": label, "hasil_prediksi": json.loads(result_json)["status"]}
            for label, result_json in rows
        ]
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"label_aktual", "hasil_prediksi"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV harus memiliki kolom label_aktual dan hasil_prediksi.")
        return list(reader)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="CSV label atau berkas SQLite aplikasi")
    args = parser.parse_args()
    try:
        result = evaluate_rows(read_records(args.dataset))
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
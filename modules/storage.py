"""Penyimpanan SQLite untuk pemeriksaan dan label dataset."""

import json
import os
import sqlite3
from pathlib import Path


def connect(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database(database_path):
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS checks (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                ocr_text TEXT NOT NULL,
                ocr_status TEXT NOT NULL,
                ocr_note TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL,
                image_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                true_label TEXT CHECK (true_label IN ('asli', 'manipulasi') OR true_label IS NULL)
            )"""
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(checks)")}
        if "ocr_note" not in columns:
            connection.execute("ALTER TABLE checks ADD COLUMN ocr_note TEXT NOT NULL DEFAULT ''")


def create_check(database_path, record):
    with connect(database_path) as connection:
        connection.execute(
            """INSERT INTO checks (
                id, created_at, original_name, stored_name, mime_type, file_size,
                width, height, ocr_text, ocr_status, ocr_note, metadata_json, image_json,
                result_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["id"], record["created_at"], record["original_name"],
                record["stored_name"], record["mime_type"], record["file_size"],
                record["width"], record["height"], record["ocr_text"],
                record["ocr_status"], record.get("ocr_note") or "",
                json.dumps(record["metadata"], ensure_ascii=False),
                json.dumps(record["image_analysis"], ensure_ascii=False),
                json.dumps(record["result"], ensure_ascii=False), record["status"],
            ),
        )


def _decode(row):
    if row is None:
        return None
    record = dict(row)
    record["metadata"] = json.loads(record.pop("metadata_json"))
    record["image_analysis"] = json.loads(record.pop("image_json"))
    record["result"] = json.loads(record.pop("result_json"))
    return record


def get_check(database_path, check_id):
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    return _decode(row)


def list_checks(database_path, limit=100):
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM checks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_decode(row) for row in rows]


def save_true_label(database_path, check_id, label):
    with connect(database_path) as connection:
        cursor = connection.execute(
            "UPDATE checks SET true_label = ? WHERE id = ?", (label, check_id)
        )
        return cursor.rowcount == 1


def delete_check(database_path, check_id, uploads_path, analysis_path):
    """Delete a record and its files, restoring moved files if the DB commit fails."""
    if len(check_id) != 32 or any(char not in "0123456789abcdef" for char in check_id):
        return False

    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT stored_name FROM checks WHERE id = ?", (check_id,)
        ).fetchone()
        if row is None:
            return False

        sources = [Path(uploads_path) / row["stored_name"]]
        sources.extend(Path(analysis_path).glob(f"{check_id}_ela.jpg"))
        moved = []
        try:
            for source in sources:
                if source.is_file():
                    quarantine = source.with_name(f".deleting-{check_id}-{source.name}")
                    os.replace(source, quarantine)
                    moved.append((source, quarantine))
            connection.execute("DELETE FROM checks WHERE id = ?", (check_id,))
            connection.commit()
        except Exception:
            connection.rollback()
            for source, quarantine in moved:
                if quarantine.exists():
                    os.replace(quarantine, source)
            raise

    for _, quarantine in moved:
        quarantine.unlink(missing_ok=True)
    return True


def labeled_records(database_path):
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT id, created_at, true_label, result_json FROM checks "
            "WHERE true_label IS NOT NULL ORDER BY created_at"
        ).fetchall()
    records = []
    for row in rows:
        result = json.loads(row["result_json"])
        records.append({
            "id": row["id"], "created_at": row["created_at"],
            "label_aktual": row["true_label"], "hasil_prediksi": result["status"],
        })
    return records

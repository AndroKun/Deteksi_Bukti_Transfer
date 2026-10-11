"""Entry point aplikasi pemeriksaan bukti transfer untuk penggunaan lokal."""

import ipaddress
import json
import hmac
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from modules import decision, image_analysis, metadata, ocr, storage

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
FORMAT_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
        DATABASE=str(Path(app.instance_path) / "database" / "checks.sqlite3"),
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        ANALYSIS_FOLDER=str(Path(app.instance_path) / "analysis"),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["ANALYSIS_FOLDER"]).mkdir(parents=True, exist_ok=True)
    storage.init_database(app.config["DATABASE"])

    @app.before_request
    def restrict_to_localhost():
        try:
            if not ipaddress.ip_address(request.remote_addr or "").is_loopback:
                abort(403)
        except ValueError:
            abort(403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("_csrf_token", "")
            provided = request.form.get("_csrf_token", "")
            if not expected or not hmac.compare_digest(expected, provided):
                abort(400, "Sesi formulir tidak valid. Muat ulang halaman lalu coba lagi.")

    @app.context_processor
    def inject_csrf_token():
        token = session.setdefault("_csrf_token", secrets.token_urlsafe(32))
        return {"csrf_token": token}

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error):
        return jsonify(error="Ukuran gambar melebihi batas 10 MB."), 413

    @app.get("/")
    def index():
        return render_template("index.html", max_upload_mb=MAX_UPLOAD_BYTES // (1024 * 1024))

    @app.post("/analyze")
    def analyze():
        uploaded = request.files.get("image")
        if not uploaded or not uploaded.filename:
            abort(400, "Pilih gambar yang akan diperiksa.")
        safe_original_name = secure_filename(Path(uploaded.filename.replace("\\", "/")).name)
        if not safe_original_name:
            abort(400, "Nama berkas tidak valid.")
        content = uploaded.stream.read(MAX_UPLOAD_BYTES + 1)
        if not content:
            abort(400, "Berkas gambar kosong.")
        if len(content) > MAX_UPLOAD_BYTES:
            abort(413, "Ukuran gambar melebihi batas 10 MB.")

        try:
            with Image.open(__import__("io").BytesIO(content)) as image:
                actual_format = image.format
                if actual_format not in ALLOWED_FORMATS:
                    abort(400, "Format gambar yang didukung: JPEG, PNG, dan WEBP.")
                image.verify()
            with Image.open(__import__("io").BytesIO(content)) as image:
                width, height = image.size
                if width * height > MAX_IMAGE_PIXELS:
                    abort(400, "Resolusi gambar melebihi batas aman 25 megapiksel.")
                image.load()
        except (UnidentifiedImageError, OSError, ValueError):
            abort(400, "Berkas bukan gambar yang valid atau gambar rusak.")

        check_id = uuid.uuid4().hex
        stored_name = f"{check_id}{FORMAT_EXTENSIONS[actual_format]}"
        upload_path = Path(app.config["UPLOAD_FOLDER"]) / stored_name
        temporary_path = upload_path.with_suffix(upload_path.suffix + ".tmp")
        temporary_path.write_bytes(content)
        os.replace(temporary_path, upload_path)

        try:
            ocr_result = ocr.extract_text(upload_path)
            metadata_result = metadata.inspect_image(upload_path)
            image_result = image_analysis.analyze_image(
                upload_path, app.config["ANALYSIS_FOLDER"], check_id
            )
            combined = decision.combine_results(ocr_result, metadata_result, image_result)
        except Exception:
            upload_path.unlink(missing_ok=True)
            Path(app.config["ANALYSIS_FOLDER"], f"{check_id}_ela.jpg").unlink(missing_ok=True)
            app.logger.exception("Analisis gagal untuk pemeriksaan %s", check_id)
            abort(500, "Analisis gambar gagal. Pastikan berkas gambar dapat dibaca.")

        record = {
            "id": check_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "original_name": safe_original_name[:255],
            "stored_name": stored_name,
            "mime_type": metadata_result["mime_type"],
            "file_size": len(content),
            "width": width,
            "height": height,
            "ocr_text": ocr_result["text"],
            "ocr_status": ocr_result["status"],
            "ocr_note": ocr_result["note"] or "",
            "metadata": metadata_result,
            "image_analysis": image_result,
            "result": combined,
            "status": "completed",
        }
        try:
            storage.create_check(app.config["DATABASE"], record)
        except Exception:
            upload_path.unlink(missing_ok=True)
            if image_result.get("heatmap_name"):
                Path(app.config["ANALYSIS_FOLDER"], image_result["heatmap_name"]).unlink(missing_ok=True)
            app.logger.exception("Gagal menyimpan pemeriksaan %s", check_id)
            abort(500, "Hasil pemeriksaan tidak dapat disimpan.")
        return redirect(url_for("result", check_id=check_id))

    @app.get("/checks/<check_id>")
    def result(check_id):
        record = storage.get_check(app.config["DATABASE"], check_id)
        if record is None:
            abort(404)
        candidates = ocr.find_candidates(record["ocr_text"])
        return render_template("result.html", record=record, candidates=candidates)

    @app.get("/history")
    def history():
        return render_template("history.html", records=storage.list_checks(app.config["DATABASE"]))

    @app.post("/checks/<check_id>/delete")
    def delete(check_id):
        try:
            removed = storage.delete_check(
                app.config["DATABASE"], check_id,
                app.config["UPLOAD_FOLDER"], app.config["ANALYSIS_FOLDER"],
            )
        except OSError:
            app.logger.exception("Gagal menghapus pemeriksaan %s", check_id)
            abort(500, "Pemeriksaan tidak dapat dihapus sepenuhnya.")
        if not removed:
            abort(404)
        return redirect(url_for("history"))

    @app.post("/checks/<check_id>/label")
    def label(check_id):
        true_label = request.form.get("true_label")
        if true_label not in {"asli", "manipulasi"}:
            abort(400, "Label harus asli atau manipulasi.")
        if not storage.save_true_label(app.config["DATABASE"], check_id, true_label):
            abort(404)
        return redirect(url_for("result", check_id=check_id))

    @app.get("/checks/<check_id>/image/<kind>")
    def image_file(check_id, kind):
        record = storage.get_check(app.config["DATABASE"], check_id)
        if record is None:
            abort(404)
        if kind == "original":
            file_path = Path(app.config["UPLOAD_FOLDER"]) / record["stored_name"]
        elif kind == "ela" and record["image_analysis"].get("heatmap_name"):
            file_path = Path(app.config["ANALYSIS_FOLDER"]) / record["image_analysis"]["heatmap_name"]
        else:
            abort(404)
        if not file_path.is_file():
            abort(404)
        return send_file(file_path, mimetype="image/jpeg" if kind == "ela" else record["mime_type"])

    @app.get("/checks/<check_id>/report.pdf")
    def report(check_id):
        record = storage.get_check(app.config["DATABASE"], check_id)
        if record is None:
            abort(404)
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from io import BytesIO

            output = BytesIO()
            document = canvas.Canvas(output, pagesize=A4)
            _, page_height = A4
            y = page_height - 48
            lines = [
                "Laporan Pemeriksaan Indikasi Manipulasi",
                f"ID pemeriksaan: {record['id']}",
                f"Waktu: {record['created_at']}",
                f"Berkas: {record['original_name']}",
                f"Hasil: {record['result']['status'].replace('_', ' ')}",
                *record["result"]["reasons"],
                "",
                "Laporan ini bukan bukti mutlak keaslian atau kepalsuan transaksi.",
                "",
                "Teks OCR:",
                record["ocr_note"],
                *(record["ocr_text"].splitlines() or ["Tidak ada teks yang terbaca."]),
                "",
                "Metadata:",
                json.dumps(record["metadata"], ensure_ascii=True, indent=2).splitlines(),
                "",
                "Analisis citra:",
                record["image_analysis"]["note"],
            ]
            for item in lines:
                entries = item if isinstance(item, list) else [item]
                for line in entries:
                    if y < 48:
                        document.showPage()
                        y = page_height - 48
                    document.drawString(48, y, str(line)[:110])
                    y -= 16
            document.save()
            output.seek(0)
            return send_file(output, mimetype="application/pdf", as_attachment=True,
                             download_name=f"laporan-{check_id[:12]}.pdf")
        except ImportError:
            abort(503, "Dependensi PDF belum terpasang.")

    @app.get("/evaluation.csv")
    def evaluation_csv():
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "created_at", "label_aktual", "hasil_prediksi"])
        writer.writeheader()
        writer.writerows(storage.labeled_records(app.config["DATABASE"]))
        from flask import Response
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=evaluasi.csv"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False)

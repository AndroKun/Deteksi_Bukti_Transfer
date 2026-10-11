from io import BytesIO
import re
import shutil
from pathlib import Path

from PIL import Image
from PIL import ImageDraw, ImageFont
import pytest
from pytesseract import get_languages

from app import create_app
from modules import storage


def make_png():
    output = BytesIO()
    Image.new("RGB", (20, 12), "white").save(output, format="PNG")
    output.seek(0)
    return output


def make_jpeg():
    output = BytesIO()
    Image.new("RGB", (32, 24), (50, 130, 90)).save(output, format="JPEG", quality=88)
    output.seek(0)
    return output


def make_receipt_jpeg():
    output = BytesIO()
    image = Image.new("RGB", (1400, 550), "white")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not Path(font_path).is_file():
        pytest.skip("Font DejaVu tidak tersedia untuk gambar OCR sintetis.")
    font = ImageFont.truetype(font_path, 48)
    for index, text in enumerate([
        "BUKTI TRANSFER", "Transfer Successful", "Nominal: Rp 125.000",
        "Date: 11/10/2026", "Penerima: SITI AMINAH",
    ]):
        draw.text((70, 45 + index * 94), text, font=font, fill="black")
    image.save(output, format="JPEG", quality=95)
    output.seek(0)
    return output


def csrf_token(client):
    page = client.get("/").get_data(as_text=True)
    return re.search(r'name="_csrf_token" value="([^"]+)"', page).group(1)


def test_upload_persists_result_image_and_deletion(tmp_path, monkeypatch):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "db.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ANALYSIS_FOLDER": str(tmp_path / "analysis"),
    })
    monkeypatch.setattr("modules.ocr.extract_text", lambda _path: {
        "text": "Transfer Rp 20.000", "status": "completed", "note": None,
    })
    client = app.test_client()
    token = csrf_token(client)
    response = client.post("/analyze", data={
        "_csrf_token": token, "image": (make_png(), "bukti.png"),
    }, content_type="multipart/form-data")
    assert response.status_code == 302
    result_url = response.headers["Location"]
    check_id = result_url.rsplit("/", 1)[-1]
    assert client.get(result_url).status_code == 200
    assert client.get("/history").status_code == 200
    files = list((tmp_path / "uploads").iterdir())
    assert len(files) == 1
    assert files[0].is_file()

    assert client.post(f"/checks/{check_id}/label", data={
        "_csrf_token": token, "true_label": "manipulasi",
    }).status_code == 302
    csv_response = client.get("/evaluation.csv")
    assert b"manipulasi" in csv_response.data

    assert client.post(f"/checks/{check_id}/delete", data={"_csrf_token": token}).status_code == 302
    assert list((tmp_path / "uploads").iterdir()) == []
    assert client.get(result_url).status_code == 404


def test_rejects_non_image_and_unsupported_format(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "db.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ANALYSIS_FOLDER": str(tmp_path / "analysis"),
    })
    client = app.test_client()
    token = csrf_token(client)
    response = client.post("/analyze", data={
        "_csrf_token": token, "image": (BytesIO(b"not an image"), "fake.png"),
    }, content_type="multipart/form-data")
    assert response.status_code == 400


def test_rejects_state_changes_without_csrf_token(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "db.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ANALYSIS_FOLDER": str(tmp_path / "analysis"),
    })
    response = app.test_client().post("/analyze", data={
        "image": (make_png(), "bukti.png"),
    }, content_type="multipart/form-data")
    assert response.status_code == 400


def test_jpeg_ela_pdf_restart_persistence_and_consistent_deletion(tmp_path, monkeypatch):
    config = {
        "TESTING": True,
        "DATABASE": str(tmp_path / "db.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ANALYSIS_FOLDER": str(tmp_path / "analysis"),
    }
    monkeypatch.setattr("modules.ocr.extract_text", lambda _path: {
        "text": "Transfer berhasil", "status": "completed", "note": None,
    })
    client = create_app(config).test_client()
    token = csrf_token(client)
    response = client.post("/analyze", data={
        "_csrf_token": token, "image": (make_jpeg(), "bukti.jpg"),
    }, content_type="multipart/form-data")
    check_id = response.headers["Location"].rsplit("/", 1)[-1]

    result_page = client.get(response.headers["Location"])
    assert result_page.status_code == 200
    assert b"PETA ELA" in result_page.data
    assert client.get(f"/checks/{check_id}/image/ela").status_code == 200
    pdf = client.get(f"/checks/{check_id}/report.pdf")
    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF")
    assert len(list((tmp_path / "analysis").glob("*_ela.jpg"))) == 1

    restarted_client = create_app(config).test_client()
    assert restarted_client.get(response.headers["Location"]).status_code == 200
    assert restarted_client.get("/history").status_code == 200
    assert client.post(f"/checks/{check_id}/delete", data={"_csrf_token": token}).status_code == 302
    assert list((tmp_path / "uploads").iterdir()) == []
    assert list((tmp_path / "analysis").iterdir()) == []


def test_detects_image_format_from_content_not_filename(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "db.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ANALYSIS_FOLDER": str(tmp_path / "analysis"),
    })
    client = app.test_client()
    token = csrf_token(client)
    response = client.post("/analyze", data={
        "_csrf_token": token, "image": (make_png(), "../../bukti.jpg"),
    }, content_type="multipart/form-data")
    assert response.status_code == 302
    stored = list((tmp_path / "uploads").iterdir())
    assert len(stored) == 1
    assert stored[0].suffix == ".png"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract belum terpasang")
def test_real_ocr_metadata_ela_and_persistence(tmp_path):
    if not {"ind", "eng"}.issubset(set(get_languages(config=""))):
        pytest.skip("Data bahasa Tesseract ind dan eng belum lengkap.")
    config = {
        "TESTING": True,
        "DATABASE": str(tmp_path / "db.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ANALYSIS_FOLDER": str(tmp_path / "analysis"),
    }
    client = create_app(config).test_client()
    token = csrf_token(client)
    response = client.post("/analyze", data={
        "_csrf_token": token, "image": (make_receipt_jpeg(), "synthetic-transfer.jpg"),
    }, content_type="multipart/form-data")
    assert response.status_code == 302
    check_id = response.headers["Location"].rsplit("/", 1)[-1]
    record = storage.get_check(config["DATABASE"], check_id)

    assert record["ocr_status"] == "completed"
    assert "Rp 125.000" in record["ocr_text"]
    assert "11/10/2026" in record["ocr_text"]
    assert record["metadata"]["format"] == "JPEG"
    assert record["metadata"]["resolution"] == {"width": 1400, "height": 550}
    assert record["image_analysis"]["available"] is True
    assert record["image_analysis"]["metrics"]["width"] == 1400
    assert record["result"]["status"] == "tidak_meyakinkan"
    assert (Path(config["UPLOAD_FOLDER"]) / record["stored_name"]).is_file()
    assert (Path(config["ANALYSIS_FOLDER"]) / record["image_analysis"]["heatmap_name"]).is_file()

    restarted_app = create_app(config)
    persisted = storage.get_check(config["DATABASE"], check_id)
    assert restarted_app.test_client().get(response.headers["Location"]).status_code == 200
    assert persisted["ocr_text"] == record["ocr_text"]
    assert persisted["metadata"] == record["metadata"]
    assert persisted["image_analysis"] == record["image_analysis"]


def test_blocks_non_loopback_requests(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "db.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ANALYSIS_FOLDER": str(tmp_path / "analysis"),
    })
    response = app.test_client().get("/history", environ_base={"REMOTE_ADDR": "203.0.113.5"})
    assert response.status_code == 403

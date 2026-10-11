"""OCR teks; temuan hasil parsing adalah kandidat, bukan fakta transaksi."""

import re

from PIL import Image


def extract_text(image_path):
    try:
        import pytesseract
        text = pytesseract.image_to_string(Image.open(image_path), lang="ind+eng")
        return {"text": text.strip(), "status": "completed", "note": None}
    except ImportError:
        return {"text": "", "status": "unavailable", "note": "Paket pytesseract belum tersedia."}
    except Exception as error:
        if error.__class__.__name__ == "TesseractNotFoundError":
            return {
                "text": "", "status": "unavailable",
                "note": "Program Tesseract belum terpasang pada server.",
            }
        if error.__class__.__name__ == "TesseractError":
            return {
                "text": "", "status": "unavailable",
                "note": "Tesseract tidak dapat memproses gambar ini atau bahasa OCR belum terpasang.",
            }
        return {"text": "", "status": "error", "note": "Teks tidak dapat dibaca dari gambar."}


def find_candidates(text):
    """Expose plausible strings for review without interpreting them as verified fields."""
    amounts = [match.strip() for match in re.findall(
        r"(?i)(?:rp\s*\d[\d., ]*|\b\d{1,3}(?:[.,]\d{3})+\b)", text
    )]
    dates = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", text
    )
    return {"nominal_kandidat": amounts[:10], "tanggal_kandidat": dates[:10]}

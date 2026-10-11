"""Analisis visual prototipe. ELA bersifat indikatif dan tidak memvonis keaslian."""

from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def analyze_image(image_path, analysis_path, check_id):
    with Image.open(image_path) as image:
        image_format = image.format
        rgb = image.convert("RGB")
        width, height = rgb.size
        if image_format != "JPEG":
            return {
                "method": "ELA",
                "available": False,
                "heatmap_name": None,
                "metrics": None,
                "indicators": [],
                "note": (
                    "ELA prototipe hanya diterapkan pada JPEG; format ini tidak dianalisis "
                    "dengan metode tersebut."
                ),
            }
        encoded = BytesIO()
        rgb.save(encoded, format="JPEG", quality=90)
        encoded.seek(0)
        with Image.open(encoded) as recompressed:
            difference = np.asarray(rgb, dtype=np.int16) - np.asarray(recompressed, dtype=np.int16)
        grayscale = cv2.cvtColor(np.abs(difference).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        mean_error = float(np.mean(grayscale))
        p95_error = float(np.percentile(grayscale, 95))
        maximum_error = int(np.max(grayscale))
        scaled = np.clip(grayscale.astype(np.float32) * 8, 0, 255).astype(np.uint8)
        heatmap = cv2.applyColorMap(scaled, cv2.COLORMAP_INFERNO)
        Path(analysis_path).mkdir(parents=True, exist_ok=True)
        heatmap_name = f"{check_id}_ela.jpg"
        if not cv2.imwrite(str(Path(analysis_path) / heatmap_name), heatmap):
            raise OSError("Gagal menyimpan visualisasi ELA")
        return {
            "method": "ELA",
            "available": True,
            "heatmap_name": heatmap_name,
            "metrics": {
                "mean_error": round(mean_error, 3),
                "p95_error": round(p95_error, 3),
                "maximum_error": maximum_error,
                "width": width,
                "height": height,
            },
            "indicators": [],
            "note": (
                "Peta menampilkan perbedaan kompresi relatif setelah simpan ulang JPEG. "
                "Pola terang tidak membuktikan penyuntingan: kompresi, konten, dan "
                "riwayat simpan dapat memengaruhinya. Belum ada ambang tervalidasi."
            ),
        }

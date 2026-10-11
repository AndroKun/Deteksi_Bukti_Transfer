"""Pembacaan properti gambar dan subset EXIF yang aman ditampilkan."""

from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image


def inspect_image(image_path):
    path = Path(image_path)
    with Image.open(path) as image:
        exif = image.getexif()
        exif_values = {}
        for tag_id, value in exif.items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if name in {"DateTime", "DateTimeOriginal", "DateTimeDigitized", "Software", "Make", "Model"}:
                exif_values[name] = str(value)[:200]
        return {
            "format": image.format or "Tidak diketahui",
            "mime_type": Image.MIME.get(image.format, "application/octet-stream"),
            "file_size": path.stat().st_size,
            "resolution": {"width": image.width, "height": image.height},
            "exif": exif_values,
            "server_copy_mtime": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(),
            "limitations": (
                "EXIF dan waktu berkas dapat hilang atau berubah saat gambar dibagikan, "
                "disunting, atau dikonversi; ketiadaannya bukan bukti manipulasi."
            ),
        }

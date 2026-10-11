# Ruang Bukti

Prototipe lokal untuk memeriksa **indikasi** manipulasi pada gambar bukti transfer. Aplikasi menggabungkan pembacaan OCR, properti berkas/EXIF, dan visualisasi ELA untuk JPEG. Aplikasi tidak memverifikasi transaksi dan tidak dapat memastikan gambar asli atau palsu.

## Arsitektur

- `app.py`: aplikasi Flask, validasi upload, halaman web, endpoint lokal, dan laporan PDF.
- `modules/`: OCR, metadata, analisis ELA, aturan keputusan, serta SQLite.
- `templates/` dan `static/`: antarmuka HTML, CSS, dan JavaScript berbahasa Indonesia.
- `instance/database/checks.sqlite3`: riwayat, hasil, dan label dataset yang persisten.
- `instance/uploads/` dan `instance/analysis/`: gambar sumber dan visualisasi; tidak disajikan sebagai folder publik.
- `tests/`: tes unit dan alur upload, penyimpanan, pelabelan, serta penghapusan.

## Instalasi

Gunakan Python 3.10 atau yang lebih baru. Dari folder proyek:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

OCR memerlukan program Tesseract di sistem selain paket Python `pytesseract`. Pada Ubuntu/Debian:

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-ind tesseract-ocr-eng
```

Periksa pemasangan dengan `tesseract --version` dan `tesseract --list-langs`. Jika Tesseract atau bahasa `ind`/`eng` tidak tersedia, pemeriksaan lain tetap berjalan dan status OCR akan ditampilkan sebagai tidak tersedia.

## Menjalankan

```bash
source .venv/bin/activate
python app.py
```

Buka `http://127.0.0.1:5000`. Server secara bawaan hanya mengikat loopback; permintaan dari jaringan lain ditolak. Jangan ubah `HOST` menjadi `0.0.0.0` atau publikasikan aplikasi ini: belum ada autentikasi pengguna. Jika aplikasi akan dipasang bersama pengguna lain, tambahkan autentikasi dan otorisasi pada riwayat, detail, unduhan, label, dan penghapusan, serta tinjau retensi dan perlindungan gambar sensitif. `SECRET_KEY` dapat diatur melalui environment variable bila diperlukan.

Gambar JPEG, PNG, dan WEBP hingga 10 MB dan 25 megapiksel diterima. Identitas format diperiksa dari konten gambar yang dapat didekode, bukan dari ekstensi. Berkas disimpan di `instance/`; direktori ini diabaikan Git. Data tetap tersedia setelah aplikasi dimulai ulang selama direktori tersebut tidak dihapus.

## Metode dan interpretasi

- **OCR:** teks mentah serta kandidat nominal/tanggal ditampilkan untuk ditinjau. OCR dapat salah baca; hasilnya bukan konfirmasi identitas, nominal, atau transaksi.
- **Metadata:** format, ukuran, dimensi, waktu salinan di server, serta subset EXIF yang tersedia. Metadata dapat hilang atau berubah saat gambar dibagikan; ketiadaannya bukan indikator pemalsuan.
- **ELA:** untuk JPEG saja, gambar disimpan ulang pada kualitas tetap lalu divisualisasikan perbedaan kompresinya. Area terang bukan bukti manipulasi. Konten, kompresi, penyuntingan, dan riwayat penyimpanan memengaruhi hasil. Format lain dilaporkan tidak dianalisis ELA.
- **Keputusan:** tidak ada skor probabilitas atau ambang yang dikarang. Status indikasi memerlukan sedikitnya dua metode independen dengan bukti dan ambang tervalidasi; status tanpa indikasi hanya boleh dipakai bila semua metode yang relevan mampu menyingkirkan indikasi dalam cakupannya. Modul saat ini belum memenuhi syarat itu, sehingga kesimpulan prototipe adalah **tidak meyakinkan**.
- Visualisasi dan ringkasan tidak menggantikan pemeriksaan manual, sumber transaksi, atau metode forensik yang telah divalidasi.

## Riwayat dan laporan

Riwayat dapat dibuka tanpa akun pada instalasi lokal. Halaman hasil menyediakan PDF. Label “asli” atau “manipulasi” hanya dicatat jika status sebenarnya diketahui; label tidak mengubah hasil analisis. CSV label dapat diunduh dari halaman riwayat atau hasil.

Evaluasi menggunakan data berlabel:

```bash
python evaluate_dataset.py instance/database/checks.sqlite3
python evaluate_dataset.py dataset.csv
```

Evaluator menerima CSV dengan kolom `label_aktual` dan `hasil_prediksi`. Label aktual: `asli` atau `manipulasi`; prediksi: `indikasi_manipulasi`, `tidak_ditemukan_indikasi`, atau `tidak_meyakinkan`. Hasil inkonklusif dikecualikan dari confusion matrix biner dan dilaporkan terpisah sebagai coverage. Accuracy, precision, recall, dan F1 dihitung hanya pada prediksi yang dapat dipetakan. Evaluasi prototipe saat ini tidak menyatakan akurasi metode: sistem belum menghasilkan prediksi kelas yang tervalidasi.

## Pengujian

```bash
python -m pytest -q
```

Tes memakai gambar sintetis kecil untuk memeriksa alur perangkat lunak; hasil tes tersebut bukan dataset forensik dan bukan bukti validasi deteksi.
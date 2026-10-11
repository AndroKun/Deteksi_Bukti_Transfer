"""Aturan keputusan gabungan; tidak ada skor atau bobot probabilistik."""


def combine_results(ocr, metadata, image_analysis, decision_evidence=None):
    """Only validated, independent evidence may drive a definitive prototype status."""
    evidence = decision_evidence or []
    reliable = [
        item for item in evidence
        if item.get("validated") is True and item.get("supports_manipulation") is True
    ]
    independent_methods = {item.get("method") for item in reliable if item.get("method")}

    if len(independent_methods) >= 2:
        status = "indikasi_manipulasi"
        reasons = ["Dua atau lebih metode independen dengan ambang tervalidasi mendukung indikasi."]
    elif all(item.get("can_rule_out") is True for item in (ocr, metadata, image_analysis)):
        status = "tidak_ditemukan_indikasi"
        reasons = ["Metode yang digunakan tidak menemukan indikator pada cakupannya."]
    else:
        status = "tidak_meyakinkan"
        reasons = [
            "Prototipe belum memiliki metode dan ambang yang tervalidasi untuk menyimpulkan "
            "ada atau tidaknya manipulasi. Hasil ini bukan konfirmasi keaslian transaksi."
        ]

    indicators = [
        {"metode": item["method"], "alasan": item.get("reason", "Indikator ditemukan.")}
        for item in reliable
    ]
    return {"status": status, "reasons": reasons, "indicators": indicators}

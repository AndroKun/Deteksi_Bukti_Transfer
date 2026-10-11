from modules.decision import combine_results
from modules.ocr import find_candidates


def test_ocr_candidates_are_only_extracted_strings():
    found = find_candidates("Nominal Rp 125.000 pada 2025-03-08")
    assert found["nominal_kandidat"] == ["Rp 125.000"]
    assert found["tanggal_kandidat"] == ["2025-03-08"]


def test_unvalidated_ela_does_not_decide_authenticity():
    result = combine_results(
        {"status": "completed"}, {"exif": {}},
        {"available": True, "indicators": [], "can_rule_out": False},
    )
    assert result["status"] == "tidak_meyakinkan"
    assert result["indicators"] == []


def test_decision_requires_two_validated_independent_methods():
    result = combine_results(
        {}, {}, {},
        [
            {"method": "ela", "validated": True, "supports_manipulation": True},
            {"method": "ocr", "validated": True, "supports_manipulation": True},
        ],
    )
    assert result["status"] == "indikasi_manipulasi"

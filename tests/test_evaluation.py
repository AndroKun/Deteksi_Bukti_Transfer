from evaluate_dataset import evaluate_rows


def test_confusion_matrix_excludes_inconclusive_predictions():
    result = evaluate_rows([
        {"label_aktual": "asli", "hasil_prediksi": "tidak_ditemukan_indikasi"},
        {"label_aktual": "manipulasi", "hasil_prediksi": "indikasi_manipulasi"},
        {"label_aktual": "manipulasi", "hasil_prediksi": "tidak_ditemukan_indikasi"},
        {"label_aktual": "asli", "hasil_prediksi": "tidak_meyakinkan"},
    ])
    assert result["confusion_matrix"]["actual_asli"] == {
        "prediksi_asli": 1, "prediksi_manipulasi": 0,
    }
    assert result["confusion_matrix"]["actual_manipulasi"] == {
        "prediksi_asli": 1, "prediksi_manipulasi": 1,
    }
    assert result["prediksi_inkonklusif_dikecualikan"] == 1
    assert result["coverage"] == 0.75
    assert result["accuracy"] == 2 / 3
    assert result["precision_manipulasi"] == 1
    assert result["recall_manipulasi"] == 0.5


def test_invalid_ground_truth_label_is_rejected():
    try:
        evaluate_rows([{"label_aktual": "mungkin", "hasil_prediksi": "tidak_meyakinkan"}])
    except ValueError as error:
        assert "label_aktual" in str(error)
    else:
        raise AssertionError("Label tidak valid seharusnya ditolak")


def test_empty_dataset_has_no_metrics():
    result = evaluate_rows([])
    assert result["jumlah_total"] == 0
    assert result["coverage"] == 0
    assert result["accuracy"] is None
    assert result["precision_manipulasi"] is None
    assert result["recall_manipulasi"] is None
    assert result["f1_manipulasi"] is None
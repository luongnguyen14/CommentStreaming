"""test_model_trial.py — Test các hàm THUẦN PYTHON của chương trình thử nghiệm.

Không dựng SparkSession: các hàm được test ở đây là quy tắc loại văn bản (giống
DLQ của streaming), tính chỉ số từ confusion matrix, và định dạng kết quả.
Phần nạp model/chấm điểm cần Spark + model thật nên được kiểm bằng cách chạy
`bash scripts/run_model_trial.sh --test-sample 50`.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.app.model_trial import (
    LABELS,
    one_line,
    prediction_records,
    resolve,
    text_problem,
)
from src.common.metrics import confusion_matrix, metrics_from_cm

CLEANING = {"min_chars": 20, "max_chars": 50}


# --- Quy tắc loại văn bản (khớp DLQ của streaming) --------------------------
def test_text_problem_empty():
    assert text_problem("", CLEANING) == "van_ban_rong_sau_lam_sach"
    assert text_problem("   \n ", CLEANING) == "van_ban_rong_sau_lam_sach"


def test_text_problem_too_short():
    assert text_problem("hello", CLEANING) == "van_ban_qua_ngan_duoi_20_ky_tu"


def test_text_problem_too_long():
    assert text_problem("x" * 51, CLEANING) == "van_ban_qua_dai_tren_50_ky_tu"


def test_text_problem_valid():
    assert text_problem("x" * 20, CLEANING) is None
    assert text_problem("x" * 50, CLEANING) is None


# --- Chỉ số từ confusion matrix --------------------------------------------
def test_confusion_matrix_counts():
    y_true = np.array([0, 0, 1, 1, 1])
    y_pred = np.array([0, 1, 1, 1, 0])
    cm = confusion_matrix(y_true, y_pred, 2)
    assert cm.tolist() == [[1, 1], [1, 2]]


def test_metrics_perfect_prediction():
    cm = np.diag([5, 3, 2])
    overall, per_class = metrics_from_cm(cm, LABELS)
    assert overall["accuracy"] == pytest.approx(1.0)
    assert overall["macro_f1"] == pytest.approx(1.0)
    assert overall["weighted_f1"] == pytest.approx(1.0)
    assert overall["n"] == 10
    for lab in LABELS:
        assert per_class[lab]["precision"] == pytest.approx(1.0)
        assert per_class[lab]["recall"] == pytest.approx(1.0)


def test_metrics_known_two_class_values():
    cm = np.array([[8, 2], [1, 9]])
    overall, pc = metrics_from_cm(cm, ["a", "b"])
    assert overall["accuracy"] == pytest.approx(0.85)
    assert pc["a"]["precision"] == pytest.approx(8 / 9)
    assert pc["a"]["recall"] == pytest.approx(0.8)
    assert pc["a"]["f1"] == pytest.approx(16 / 19)
    assert pc["b"]["precision"] == pytest.approx(9 / 11)
    assert pc["b"]["recall"] == pytest.approx(0.9)
    assert pc["b"]["f1"] == pytest.approx(6 / 7)
    assert overall["macro_f1"] == pytest.approx((16 / 19 + 6 / 7) / 2)
    assert overall["weighted_f1"] == pytest.approx((16 / 19 + 6 / 7) / 2)
    assert overall["macro_precision"] == pytest.approx((8 / 9 + 9 / 11) / 2)
    assert overall["macro_recall"] == pytest.approx((0.8 + 0.9) / 2)


def test_metrics_absent_class_is_excluded_from_macro():
    # Chỉ có 2 lớp xuất hiện trong mẫu -> macro chỉ tính trên 2 lớp đó.
    cm = np.array([[5, 0, 0], [0, 3, 0], [0, 0, 0]])
    overall, _ = metrics_from_cm(cm, LABELS)
    assert overall["accuracy"] == pytest.approx(1.0)
    assert overall["macro_f1"] == pytest.approx(1.0)
    assert overall["labels_in_macro"] == "negative,neutral"


# --- Định dạng / ghi kết quả ------------------------------------------------
def test_one_line_collapses_whitespace_and_truncates():
    assert one_line("a\n b\tc") == "a b c"
    out = one_line("x" * 30, width=10)
    assert len(out) == 10
    assert out.endswith("…")


def test_resolve_relative_to_project_root():
    from src.common.utils import PROJECT_ROOT
    assert resolve("outputs/models") == PROJECT_ROOT / "outputs/models"
    assert resolve("/tmp/x") == resolve("/tmp/x")


def _row(**over):
    row = {
        "comment_id": "rw1", "label_true": "positive", "label_pred": "positive",
        "probs": {"negative": 0.1, "neutral": 0.2, "positive": 0.7},
        "confidence": 0.7, "text": "a" * 300,
    }
    row.update(over)
    return row


def test_prediction_records_hide_text_by_default():
    recs = prediction_records([_row()], "2026-01-01T00:00:00", "batch", "-", keep_text=False)
    assert "text_excerpt" not in recs[0]
    assert recs[0]["correct"] is True
    assert recs[0]["prob_positive"] == pytest.approx(0.7)


def test_prediction_records_keep_text_truncates_to_200():
    recs = prediction_records([_row()], "2026-01-01T00:00:00", "batch", "-", keep_text=True)
    assert len(recs[0]["text_excerpt"]) == 200


def test_prediction_records_no_true_label_leaves_correct_blank():
    recs = prediction_records([_row(label_true="")], "2026-01-01T00:00:00", "batch", "-",
                              keep_text=False)
    assert recs[0]["correct"] == ""

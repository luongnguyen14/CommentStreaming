"""metrics.py — Tính chỉ số phân loại từ confusion matrix, dùng chung cho
`src/training/train.py` và chương trình thử nghiệm `src/app/model_trial.py`.

Vì sao tách ra file riêng: báo cáo cuối dùng số của mô hình đã huấn luyện, còn
chương trình demo đo lại trên một mẫu. Hai nơi phải tính **cùng một công thức**
(accuracy / macro-F1 / weighted-F1 / P-R-F1 từng lớp), nếu không các con số sẽ
lệch nhau mà không ai biết vì sao.

Chỉ dùng numpy, không phụ thuộc Spark — nhờ vậy test được bằng dữ liệu nhỏ và
chạy được cả khi không dựng SparkSession.
"""

from __future__ import annotations

import numpy as np


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, n_labels: int) -> np.ndarray:
    """Ma trận nhầm lẫn `cm[i, j]` = số mẫu nhãn thật i bị đoán thành j."""
    cm = np.zeros((n_labels, n_labels), dtype=np.int64)
    np.add.at(cm, (y_true, y_pred), 1)
    return cm


def metrics_from_cm(cm: np.ndarray, labels: list[str]) -> tuple[dict, dict]:
    """Trả về (chỉ số tổng, chỉ số từng lớp) — TẤT CẢ tính từ confusion matrix.

    precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2PR/(P+R) (0 nếu mẫu số = 0).
    macro-* = trung bình cộng đều các lớp có mặt; weighted-* = trung bình theo số mẫu.
    """
    total = int(cm.sum())
    per_class: dict[str, dict] = {}
    for i, lab in enumerate(labels):
        tp = int(cm[i, i])
        fp = int(cm[:, i].sum() - tp)
        fn = int(cm[i, :].sum() - tp)
        support = int(cm[i, :].sum())
        precision = tp / (tp + fp) if tp + fp > 0 else 0.0
        recall = tp / (tp + fn) if tp + fn > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
        per_class[lab] = {
            "precision": precision, "recall": recall, "f1": f1,
            "support": support, "share": support / total if total else 0.0,
        }
    present = [lab for lab in labels if per_class[lab]["support"] > 0]
    macro = {
        m: float(np.mean([per_class[lab][m] for lab in present])) if present else 0.0
        for m in ("precision", "recall", "f1")
    }
    weighted_f1 = float(sum(per_class[lab]["f1"] * per_class[lab]["support"]
                            for lab in present) / total) if total else 0.0
    overall = {
        "n": total,
        "accuracy": float(np.trace(cm) / total) if total else 0.0,
        "weighted_f1": weighted_f1,
        "macro_f1": macro["f1"],
        "macro_precision": macro["precision"],
        "macro_recall": macro["recall"],
        "labels_in_macro": ",".join(present),
    }
    return overall, per_class

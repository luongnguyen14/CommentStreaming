# outputs/figures — Biểu đồ

PNG **200 dpi**, chữ tiếng Anh, nhãn trục có đơn vị, bảng màu nhất quán toàn dự án.
Đánh số thứ tự: `01_`, `02_`, `03_`... (`00_pipeline_architecture.png` là sơ đồ kiến trúc.)

Mỗi biểu đồ phải kèm 1–2 câu insight dựa trên số liệu thật trong `outputs/insights.md`.

| File | Nội dung |
|---|---|
| `00_pipeline_architecture.png` | Sơ đồ kiến trúc pipeline (Task 5) |
| `01_confusion_matrix.png` | Ma trận nhầm lẫn chuẩn hóa theo hàng (Task 7) |
| `02_per_class_prf1.png` | Precision / Recall / F1 từng lớp (Task 7) |
| `03_model_comparison.png` | So sánh 5 mô hình theo macro-F1 trên validation (Task 7) |
| `04_top_features.png` | 20 từ trọng số lớn nhất mỗi lớp (Task 7) |
| `05_error_reasons.png` | Nhóm nguyên nhân của 30 bình luận đoán sai (Task 7) |

Vẽ lại hình Task 7 mà không cần huấn luyện lại:
`$VENV_PY src/training/train.py --figures-only` (đọc từ `outputs/tables/*.csv`).

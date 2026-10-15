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

| `06_class_distribution.png` | Phân bố nhãn cảm xúc của dữ liệu huấn luyện (Task 9) |
| `07_length_by_class.png` | Phân bố độ dài bình luận theo lớp (Task 9) |
| `08_top_words_by_class.png` | 20 từ đặc trưng nhất mỗi lớp, xếp theo log-odds (Task 9) |
| `09_emoji_by_class.png` | Emoji theo lớp cảm xúc, dạng ô nhiệt (Task 9) |
| `10_sentiment_timeline.png` | Cảm xúc theo thời gian từ đầu ra streaming (Task 9) |
| `11_throughput_burst.png` | Thông lượng mỗi giây + đánh dấu các đợt bùng nổ (Task 9) |
| `12_negative_share_alert.png` | Tỷ lệ tiêu cực + ngưỡng cảnh báo và các điểm vượt ngưỡng (Task 9) |
| `13_latency_distribution.png` | Phân bố độ trễ end-to-end p50/p95/p99 (Task 9) |
| `14_model_quality.png` | Confusion matrix + P/R/F1 từng lớp, lấy lại từ Task 7 (Task 9) |
| `15_sentiment_timeline.html` | Bản tương tác plotly của hình 10 — HTML tự chứa, mở bằng trình duyệt (Task 9) |

Vẽ lại hình Task 7 mà không cần huấn luyện lại:
`$VENV_PY src/training/train.py --figures-only` (đọc từ `outputs/tables/*.csv`).

Vẽ lại hình Task 9 (**không cần Spark**, chỉ đọc lại `outputs/tables/eda_*.csv`):
`$VENV_PY src/eda/plots.py` — hoặc `--only 12` để vẽ lại một hình mà không ghi đè `outputs/insights.md`.

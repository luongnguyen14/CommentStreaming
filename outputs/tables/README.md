# outputs/tables — Bảng kết quả

CSV do code sinh ra. **Mọi con số trong báo cáo/slide phải lấy từ các file thật ở đây.**

## Task 5–6 (dữ liệu)

| File | Nội dung |
|---|---|
| `ingestion_report.csv` | Thông lượng producer theo từng mức `--rate` |
| `cleaning_log.csv` | Số dòng bị loại ở từng bước làm sạch (9 bước) |
| `class_distribution.csv` | Phân bố lớp ở train/val/test (+ dòng `ALL`) |
| `clean_sample.csv` | 1.000 dòng mẫu `text_raw` cạnh `text` đã sạch để đối chiếu bằng mắt |
| `emoji_frequency.csv` | 30 emoji phổ biến nhất |

## Task 7 (huấn luyện)

| File | Nội dung |
|---|---|
| `model_results.csv` | Accuracy / weighted F1 / macro-F1 của 5 mô hình (val + test), tham số tốt nhất, thời gian học, thời gian dự đoán / 10.000 bình luận |
| `per_class_metrics.csv` | Precision / Recall / F1 / số mẫu từng lớp |
| `confusion_matrix.csv` | Ma trận nhầm lẫn (số đếm + tỷ lệ theo hàng) |
| `top_features.csv` | 20 từ có trọng số lớn nhất mỗi lớp (mô hình tuyến tính) |
| `error_analysis.csv` | 30 bình luận đoán sai (ẩn danh) + nhóm nguyên nhân |
| `leak_check.json` | Số văn bản trùng nhau giữa các tập (kỳ vọng 0) |
| `test_eval_log.csv` | **Nhật ký mọi lần chạm tập test** — quy tắc "test dùng một lần" (CLAUDE.md §6) |
| `leakage_alert.txt` | Chỉ xuất hiện nếu macro-F1 vượt ngưỡng nghi rò rỉ (hiện **không có**) |

## Task 8 (streaming)

| File | Nội dung |
|---|---|
| `stream_batches.csv` | Mỗi micro-batch của mỗi query một dòng (do `StreamingQueryListener` ghi): số bản ghi vào, tốc độ, thời gian trigger, `num_rows_dropped_by_watermark`, số phần tử state — lọc theo cột `run_name` |
| `stream_verification.csv` | Kết quả đối chiếu của `verify_stream.py`: `chấm điểm + DLQ = đã gửi`, đếm message Kafka theo chênh lệch offset, chỉ số trên luồng vs offline, độ trễ, watermark |
| `stream_per_class_metrics.csv` | P/R/F1/support từng lớp, ba phạm vi: `stream`, `offline_same_ids`, `offline_full_test` |
| `stream_sample_rows.csv` | 20 dòng mẫu (ẩn danh: không có văn bản gốc, chỉ `text_len`) |
| `stream_dlq_rows.csv` | Từng bản ghi DLQ: `comment_id`, lý do, partition + offset Kafka để truy vết |

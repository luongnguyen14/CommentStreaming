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

## Task 9 (EDA — `eda_*.csv`)

Do `src/eda/queries.py` chạy Spark SQL ghi ra; **bảng số liệu nền của từng hình** (CLAUDE.md §8).
Phần lớn có cột `split` (`train`/`val`/`test`) — hình dùng `train` trừ khi ghi chú khác.

| File | Hình | Nội dung |
|---|---|---|
| `eda_overview.csv` | — | Số kiểm tra quy mô: số bình luận, số phim, độ dài mỗi tập (không vẽ hình) |
| `eda_class_distribution.csv` | 06 | Số bình luận + tỷ lệ mỗi lớp ở train/val/test |
| `eda_length_quantiles.csv` | 07 | Phân vị độ dài (token) theo lớp: p50, p75, p90, p95, p99... |
| `eda_length_histogram.csv` | 07 | Histogram độ dài theo lớp (bin rộng 50 token) |
| `eda_top_words_by_class.csv` | 08 | 20 từ đặc trưng nhất mỗi lớp + điểm log-odds, tần suất, số bình luận chứa từ |
| `eda_emoji_by_class.csv` | 09 | Emoji theo lớp: `rk_in_class`, `rk_global`, số lần, `pct_comments_with_emoji`, `emoji_per_1000_comments` |
| `eda_sentiment_per_minute.csv` | 10 | Cửa sổ nhảy 1 phút: số bình luận mỗi lớp + tỷ lệ |
| `eda_sentiment_per_10s.csv` | 10 | Cửa sổ trượt 10 giây: số bình luận mỗi lớp + tỷ lệ (thấy diễn biến bên trong phút) |
| `eda_throughput_per_second.csv` | 11 | Số bình luận mỗi giây + cột đánh dấu bùng nổ + ngưỡng |
| `eda_negative_share_alert.csv` | 12 | Tỷ lệ tiêu cực mỗi cửa sổ 10 giây + cột `alert` + lý do (đủ số bình luận hay không) |
| `eda_latency_quantiles.csv` | 13 | Phân vị độ trễ end-to-end và từng chặng (Kafka, hàng đợi, chấm điểm) |
| `eda_latency_histogram.csv` | 13 | Histogram độ trễ theo bậc 10 |
| `eda_model_quality.csv` | 14 | Ghép `per_class_metrics.csv` + `confusion_matrix.csv` của Task 7 thành một bảng cho hình |
| `eda_token_vocab.csv` | — | Hạn chế bước tách từ: kích thước từ vựng trước/sau, % token dính dấu câu (không vẽ hình) |

SQL nguyên văn (để đưa vào báo cáo): `src/eda/sql/q00_…q12_*.sql`.
File `*_sample.csv` sinh ra khi chạy `queries.py --sample N` — **số liệu chạy thử, không dùng cho báo cáo** (đã xóa).

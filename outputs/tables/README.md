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

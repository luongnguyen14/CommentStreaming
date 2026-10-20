# SentimentGuard — CommentStreaming

**Phân loại cảm xúc bình luận trực tuyến theo thời gian thực** để phát hiện sớm các
đợt bùng phát bình luận tiêu cực trong livestream/cộng đồng trực tuyến.

- **Nhóm 6** — Samsung Innovation Campus, Big Data Course.
- Thành viên: Vàng A Ký (Nhóm trưởng); Nguyễn Đình Bằng; Vàng Thị Dẳm;
  Dương Thị Hạnh; Ngô Lương Nguyên.
- Đề tài: *Mô hình phân loại cảm xúc dựa trên bình luận trực tuyến*.

> **Dữ liệu streaming trong repo là replay** từ review IMDb công khai (CC0), không
> phải bình luận livestream thật. **Exactly-once chưa kiểm chứng**; chỉ khẳng định
> at-least-once.

---

## Chạy nhanh dashboard (không cần Kafka)

Yêu cầu: **Python 3.11**, Java 8, Spark 3.5.9 (cho tab Try It).

```bash
git clone https://github.com/luongnguyen14/CommentStreaming.git
cd CommentStreaming

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Chỉ trên máy gốc (/home/hadoop/...):
source scripts/env.sh

python -m streamlit run src/app/app.py \
  --server.address 0.0.0.0 --server.port 8501
```

Mở <http://localhost:8501>. Chọn lần chạy `demo` hoặc `verify1` ở sidebar.

Repo đã có sẵn model (`outputs/models/sentiment_pipeline`, ~904 KB) và dữ liệu
dashboard (`outputs/stream/`, ~71 MB). **Không cần** tải dữ liệu thô để xem dashboard.

---

## Xem toàn bộ quy trình ngay trong terminal (không cần Kafka)

App terminal đi qua **8 giai đoạn** bằng đúng code của hệ thống: lấy mẫu replay →
đóng gói message → `from_json` + DLQ → `clean_text()` → chấm từng bình luận bằng
`PipelineModel` → cửa sổ event time + cảnh báo → sink Parquet → tổng kết. Mỗi bước
có breadcrumb để nhìn là biết đang ở đâu.

```bash
bash scripts/run_terminal_app.sh                     # nhấn Enter sau mỗi giai đoạn
bash scripts/run_terminal_app.sh --auto              # tự chạy liên tục
bash scripts/run_terminal_app.sh --fast --limit 20   # nhanh
bash scripts/run_comment_stream.sh                   # từng comment: đến đâu, kết quả ngay
bash scripts/run_terminal_app.sh --stage 5           # chỉ chấm điểm
bash scripts/run_terminal_app.sh --text "not bad at all actually"  # chấm một câu
bash scripts/run_terminal_app.sh --live --duration 60  # theo dõi Kafka (nếu đang chạy)
```

Hướng dẫn từng giai đoạn + kịch bản demo 5 phút:
[`docs/huong_dan_terminal_app.md`](docs/huong_dan_terminal_app.md).

---

## Chạy toàn bộ demo (Kafka → Streaming → Dashboard)

```bash
cd /home/hadoop/capstone
source scripts/env.sh
bash scripts/check_env.sh
bash scripts/run_demo.sh --duration 600     # tự dừng sạch sau 10 phút
bash scripts/run_demo.sh --stop
```

Dashboard: <http://localhost:8501>. Chi tiết: [`src/app/README.md`](src/app/README.md).

---

## Cấu trúc chính

| Thư mục | Nội dung |
|---|---|
| `src/training/` | Chuẩn bị dữ liệu + huấn luyện Spark ML |
| `src/streaming/` | Spark Structured Streaming (6 query, event time, watermark, DLQ) |
| `src/producer/` | Kafka producer replay/live |
| `src/app/` | Dashboard Streamlit 3 tab + app terminal walkthrough 8 giai đoạn |
| `src/eda/` | Truy vấn Spark SQL + biểu đồ |
| `src/common/` | Làm sạch văn bản dùng chung, schema, tiện ích |
| `outputs/` | Model, bảng kết quả, biểu đồ, dữ liệu streaming |
| `docs/` | Tài liệu nội bộ và hướng dẫn |
| `deliverables/` | Sản phẩm nộp theo template của giảng viên |

---

## Tài liệu

| File | Nội dung |
|---|---|
| [`docs/huong_dan_terminal_app.md`](docs/huong_dan_terminal_app.md) | App terminal: walkthrough 8 giai đoạn, phần thật/mô phỏng, kịch bản demo |
| [`docs/giai_thich_chuong_trinh.docx`](docs/giai_thich_chuong_trinh.docx) | Giải thích toàn bộ chương trình (45 trang): lệnh, tham số, luồng hoạt động, đầu ra, xử lý sự cố |
| [`docs/huong_dan_share_streamlit.md`](docs/huong_dan_share_streamlit.md) | Chia sẻ dashboard cho máy khác: LAN, ngrok, Cloudflare, cài độc lập |
| [`docs/huong_dan_lay_file_word.md`](docs/huong_dan_lay_file_word.md) | Tải file Word, mở bằng Word/LibreOffice, chạy lại trên máy gốc/máy mới |
| [`docs/bao_cao_ky_thuat_vi.md`](docs/bao_cao_ky_thuat_vi.md) | Tóm tắt báo cáo kỹ thuật tiếng Việt (bản đầy đủ: `.docx`/`.pdf`) |
| [`docs/huong_dan_bao_cao.md`](docs/huong_dan_bao_cao.md) | Hướng dẫn báo cáo trước hội đồng |
| [`docs/bao_cao_tien_do.md`](docs/bao_cao_tien_do.md) | Kịch bản báo cáo tiến độ + 30 câu Q&A |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Từ điển dữ liệu |
| [`outputs/insights.md`](outputs/insights.md) | Insight EDA kèm số liệu thật |
| [`outputs/streaming_summary.md`](outputs/streaming_summary.md) | Kiểm chứng streaming chi tiết |

---

## Kết quả chính (test set, dùng một lần)

| Chỉ số | Giá trị |
|---|---|
| Accuracy | 0,7018 |
| Macro-F1 | 0,6233 |
| Weighted-F1 | 0,7213 |
| F1 negative / neutral / positive | 0,672 / 0,378 / 0,819 |

Nguồn: `outputs/tables/model_results.csv`, `outputs/tables/per_class_metrics.csv`.

---

## Yêu cầu hệ thống

| Thành phần | Phiên bản | Ghi chú |
|---|---|---|
| Python | 3.11 | Không dùng 3.14 với PySpark 3.5.9 |
| Java | 8 | Spark 3.5.9 |
| Spark | 3.5.9 | Bắt buộc khớp phiên bản model |
| Kafka | 4.3.1 (KRaft) | Chỉ cần cho streaming/demo đầy đủ; cần Java 17 |

---

## Lưu ý trung thực

1. Nhãn được **suy từ rating IMDb** (1–4 negative, 5–6 neutral, 7–10 positive), không
   phải nhãn cảm xúc gán tay; lớp neutral rất nhiễu.
2. Mô hình túi từ **không hiểu phủ định/mỉa mai**; 14/30 lỗi phân tích là do phủ định.
3. **11.427/111.087 người dùng** xuất hiện ở hơn một tập (75.939 dòng, 41,0%) — đã đo,
   chưa loại bỏ hoàn toàn.
4. Dữ liệu streaming là **replay**, không phải livestream thật.
5. **Exactly-once chưa kiểm chứng**; chỉ khẳng định at-least-once.
6. Độ trễ p95 trên luồng đo được **9,7 giây**; nút thắt là hàng đợi xử lý.

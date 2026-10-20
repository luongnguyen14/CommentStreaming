# outputs/terminal_demo — kết quả app terminal

Thư mục này do `src/app/terminal_app.py` sinh ra khi chạy walkthrough (giai đoạn 7).
Mỗi lần chạy tạo một thư mục `run_YYYYmmdd_HHMMSS/` gồm:

| File | Nội dung |
|---|---|
| `predictions.csv` | nhãn thật/dự đoán, xác suất 3 lớp, đúng/sai, latency mô phỏng |
| `dlq.csv` | offset, `comment_id`, lý do DLQ, ghi chú của 4 bản ghi lỗi cố ý |
| `windows_sample.csv` | cửa sổ 1 phút trên mẫu nhỏ |
| `run_summary.md` | tóm tắt lần chạy + điều đã đo/chưa đo |

Các thư mục `run_*/` **không commit** (xem `.gitignore`) vì mỗi lần chạy lại sinh thêm;
muốn giữ bằng chứng thì copy file cần thiết sang `outputs/tables/`.

Lưu ý:

- Dữ liệu là **replay review IMDb công khai**, không phải livestream thật.
- `latency_ms` là độ trễ **mô phỏng offline** (gồm khởi động Spark/nạp model), không
  phải latency streaming thật. Latency thật của `verify1` nằm ở
  `outputs/stream/verify1/` và được in ở giai đoạn 6.
- Mặc định **không ghi văn bản**; chỉ dùng `--keep-text` với dữ liệu công khai.

Chạy lại: `bash scripts/run_terminal_app.sh` — hướng dẫn đầy đủ ở
[`docs/huong_dan_terminal_app.md`](../../docs/huong_dan_terminal_app.md).

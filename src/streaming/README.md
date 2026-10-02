# src/streaming — Spark Structured Streaming

- `stream_job.py` — đọc `comments_raw`, parse JSON theo schema tường minh, làm sạch, chấm điểm bằng PipelineModel

Ba đầu ra, **mỗi query một `checkpointLocation` riêng** trong `checkpoints/`:
1. Parquet chi tiết (phân vùng theo ngày/giờ)
2. Topic `comments_scored`
3. Tổng hợp theo cửa sổ thời gian + watermark

⚠️ Dùng **event time**, không dùng processing time. Bản ghi lỗi -> DLQ.
⚠️ **Không khẳng định exactly-once nếu chưa kiểm chứng bằng thực nghiệm.**

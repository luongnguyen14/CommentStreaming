# outputs/models — Mô hình đã lưu

- `sentiment_pipeline/` — Spark `PipelineModel` tốt nhất (gồm cả TF-IDF đã fit trên tập train)
- metadata JSON kèm theo: ánh xạ nhãn, tham số, phiên bản Spark, kích thước tập, ngày huấn luyện

⚠️ `src/streaming` nạp đúng model ở đây qua `--model-path`.

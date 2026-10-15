-- q10_latency_quantiles.sql — Phân vị độ trễ end-to-end (p50, p95, p99)
--
-- Hình    : outputs/figures/13_latency_distribution.png
-- Bảng ra : outputs/tables/eda_latency_quantiles.csv
-- Nguồn   : stream_detail (bảng chi tiết của lần chạy {{streaming_run}})
--
-- Định nghĩa độ trễ (đã ghi ở outputs/streaming_summary.md §5 và
-- src/streaming/README.md §7):
--   latency_ms       = giờ xử lý − event_time, đo ở mức MICRO-BATCH
--                      (mọi bản ghi trong cùng một micro-batch có cùng
--                      processing_ts, nên đây là độ trễ của lô, không phải của
--                      từng bản ghi)
--   kafka_latency_ms = mốc thời gian broker Kafka gắn − event_time
--                      (thời gian bản ghi nằm trong topic trước khi được đọc)
--   queue_latency_ms = latency_ms − kafka_latency_ms (thời gian chờ trong hàng
--                      đợi của Spark + xử lý)
-- Cột `label` chỉ là nhãn văn bản cho dòng ("all" = toàn bộ, "injected_late" =
-- 2 bản ghi cố tình đẩy trễ 10 phút dùng để thử watermark) — KHÔNG phải nhãn
-- cảm xúc.

WITH scoped AS (
    SELECT 'all' AS label, latency_ms, kafka_latency_ms, queue_latency_ms FROM stream_detail
    UNION ALL
    SELECT 'injected_late', latency_ms, kafka_latency_ms, queue_latency_ms
    FROM stream_detail WHERE kafka_latency_ms > 60000
)
SELECT
    label,
    count(*)                              AS n_comments,
    min(latency_ms)                       AS min_ms,
    percentile_approx(latency_ms, 0.50)   AS p50_ms,
    percentile_approx(latency_ms, 0.90)   AS p90_ms,
    percentile_approx(latency_ms, 0.95)   AS p95_ms,
    percentile_approx(latency_ms, 0.99)   AS p99_ms,
    max(latency_ms)                       AS max_ms,
    round(avg(latency_ms), 1)             AS mean_ms,
    percentile_approx(kafka_latency_ms, 0.50) AS kafka_p50_ms,
    percentile_approx(kafka_latency_ms, 0.95) AS kafka_p95_ms,
    percentile_approx(queue_latency_ms, 0.50) AS queue_p50_ms,
    percentile_approx(queue_latency_ms, 0.95) AS queue_p95_ms,
    min(queue_latency_ms)                 AS queue_min_ms
FROM scoped
GROUP BY label
ORDER BY label

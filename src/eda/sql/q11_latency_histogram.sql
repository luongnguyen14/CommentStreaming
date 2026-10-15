-- q11_latency_histogram.sql — Phân bố độ trễ end-to-end theo khoảng (thang log)
--
-- Hình    : outputs/figures/13_latency_distribution.png
-- Bảng ra : outputs/tables/eda_latency_histogram.csv
-- Nguồn   : stream_detail (bảng chi tiết của lần chạy {{streaming_run}})
--
-- Chia khoảng theo BẬC 10 (log10): mỗi bậc 10× chia thành
-- {{latency_bins_per_decade}} khoảng, mỗi khoảng rộng 10^(1/{{latency_bins_per_decade}}) ≈ 1,58×.
-- Phải dùng thang log vì độ trễ trải từ ~40 ms đến ~600.000 ms (2 bản ghi cố
-- tình đẩy trễ 10 phút) — chia khoảng tuyến tính thì toàn bộ dữ liệu thật dồn
-- vào cột đầu tiên và hình vô nghĩa.
--
-- Cột `n_injected_late` đếm số bản ghi trong khoảng có kafka_latency_ms > 60 s,
-- tức là bản ghi đến muộn do scripts/send_bad_events.py gửi (KHÔNG phải độ trễ
-- tự nhiên của hệ thống) — dùng để chú thích đúng trên hình.

WITH binned AS (
    SELECT
        floor(log10(greatest(latency_ms, 1)) * {{latency_bins_per_decade}}) AS bin_idx,
        latency_ms,
        kafka_latency_ms
    FROM stream_detail
)
SELECT
    bin_idx,
    round(pow(10, bin_idx / {{latency_bins_per_decade}}), 1)         AS bin_lower_ms,
    round(pow(10, (bin_idx + 1) / {{latency_bins_per_decade}}), 1)   AS bin_upper_ms,
    count(*)                                                         AS n_comments,
    sum(CASE WHEN kafka_latency_ms > 60000 THEN 1 ELSE 0 END)        AS n_injected_late
FROM binned
GROUP BY bin_idx
ORDER BY bin_idx

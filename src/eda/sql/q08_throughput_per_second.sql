-- q08_throughput_per_second.sql — Thông lượng theo giây + đánh dấu đợt bùng nổ
--
-- Hình    : outputs/figures/11_throughput_burst.png
-- Bảng ra : outputs/tables/eda_throughput_per_second.csv
-- Nguồn   : stream_detail (bảng chi tiết của lần chạy {{streaming_run}}),
--           gộp theo GIÂY của event_time (event time, không phải giờ xử lý).
--
-- Quy tắc đánh dấu bùng nổ (lấy từ config, mục eda.burst):
--     ngưỡng = trung bình + {{burst_sigma}} × độ lệch chuẩn của CHÍNH lần chạy
-- Trung bình/độ lệch chuẩn tính trên các giây CÓ dữ liệu (giây không có bình
-- luận nào không được tính là một quan sát 0, vì lúc đó luồng đang nghỉ chứ
-- không phải "không có ai bình luận").
-- Cột `configured_burst_ceiling` = replay.rate × replay.burst_factor trong
-- config = trần lý thuyết của một đợt bùng nổ do producer tạo ra; đối chiếu
-- đỉnh ĐO ĐƯỢC với con số này để kiểm tra bộ phát có đúng thiết kế không.

WITH per_second AS (
    SELECT date_trunc('second', event_time) AS second_utc, count(*) AS n_comments
    FROM stream_detail
    GROUP BY date_trunc('second', event_time)
),
stats AS (
    SELECT avg(n_comments)      AS mean_per_sec,
           stddev_pop(n_comments) AS sd_per_sec,
           max(n_comments)      AS peak_per_sec,
           count(*)             AS n_seconds_with_data
    FROM per_second
)
SELECT
    p.second_utc,
    p.n_comments,
    round(s.mean_per_sec, 2)                                        AS mean_per_sec,
    round(s.sd_per_sec, 2)                                          AS sd_per_sec,
    round(s.mean_per_sec + {{burst_sigma}} * s.sd_per_sec, 2)        AS burst_threshold,
    s.peak_per_sec,
    s.n_seconds_with_data,
    p.n_comments > s.mean_per_sec + {{burst_sigma}} * s.sd_per_sec   AS is_burst,
    {{burst_ceiling}}                                                AS configured_burst_ceiling
FROM per_second p
CROSS JOIN stats s
ORDER BY p.second_utc

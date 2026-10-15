-- q09_negative_share_alert.sql — Tỷ lệ tiêu cực theo thời gian + ngưỡng cảnh báo
--
-- Hình    : outputs/figures/12_negative_share_alert.png
-- Bảng ra : outputs/tables/eda_negative_share_alert.csv
-- Nguồn   : window_sliding_10s (cửa sổ trượt 10 giây, bước 5 giây)
--
-- Vì sao dùng cửa sổ trượt 10 giây mà không dùng cửa sổ 1 phút: cần đủ bình luận
-- trong mỗi cửa sổ để tỷ lệ có ý nghĩa, nhưng cũng cần đủ mịn để bắt đỉnh.
-- Cửa sổ 1 phút của lần chạy này chỉ có 1 điểm lớn; cửa sổ 10 giây cho ~8 điểm.
--
-- Ngưỡng cảnh báo = {{alert_threshold}} (config eda.alert, căn cứ:
-- {{alert_basis}}).
-- Điều kiện cảnh báo: tỷ lệ tiêu cực > ngưỡng VÀ cửa sổ có ít nhất
-- {{alert_min_comments}} bình luận. Điều kiện thứ hai bắt buộc: cửa sổ chỉ có
-- 1 bình luận thì tỷ lệ luôn là 0% hoặc 100% — đã thấy thật ở Task 8 (các bản
-- ghi nhịp tim đơn lẻ), cảnh báo dựa vào đó là báo động giả.
--
-- Bảng trả về TẤT CẢ các cửa sổ (kèm cột is_alert) để hình vẽ được cả những
-- cửa sổ bị loại vì quá ít bình luận.

WITH per_window AS (
    SELECT
        window_start,
        window_end,
        sum(n_comments)                    AS n_comments,
        sum(n_negative)                    AS n_negative,
        round(sum(n_negative) / sum(n_comments), 4) AS share_negative
    FROM window_sliding_10s
    GROUP BY window_start, window_end
)
SELECT
    window_start,
    window_end,
    n_comments,
    n_negative,
    share_negative,
    {{alert_threshold}}                                        AS alert_threshold,
    {{alert_min_comments}}                                     AS min_comments,
    (n_comments >= {{alert_min_comments}})                     AS has_enough_volume,
    (share_negative > {{alert_threshold}}
     AND n_comments >= {{alert_min_comments}})                 AS is_alert
FROM per_window
ORDER BY window_start

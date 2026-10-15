-- q03_length_histogram.sql — Biểu đồ phân bố độ dài bình luận theo lớp
--
-- Hình    : outputs/figures/07_length_by_class.png
-- Bảng ra : outputs/tables/eda_length_histogram.csv
-- Nguồn   : train (data/processed/train.parquet), cột `n_tokens`
-- Tham số : {{length_bin_width}} token mỗi khoảng, gộp vào khoảng cuối ở
--           {{length_bin_max}} token (đuôi dài: p95 của train ~441 token).
--
-- Đếm theo KHOẢNG cố định để ba lớp so sánh được với nhau trên cùng trục;
-- chia theo tỷ lệ phần trăm sẽ làm sai lệch so sánh vì ba lớp có số mẫu rất
-- khác nhau (positive 61%, neutral 14%).

SELECT
    label,
    least(floor(n_tokens / {{length_bin_width}}) * {{length_bin_width}},
          {{length_bin_max}})                                  AS bin_lower_tokens,
    count(*)                                                   AS n_comments,
    round(count(*) / sum(count(*)) OVER (PARTITION BY label), 4) AS share_in_class
FROM train
GROUP BY
    label,
    least(floor(n_tokens / {{length_bin_width}}) * {{length_bin_width}},
          {{length_bin_max}})
ORDER BY label, bin_lower_tokens

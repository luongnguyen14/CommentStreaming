-- q02_length_quantiles.sql — Thống kê độ dài bình luận theo lớp cảm xúc
--
-- Hình    : outputs/figures/07_length_by_class.png
-- Bảng ra : outputs/tables/eda_length_quantiles.csv
-- Nguồn   : train (data/processed/train.parquet), cột `n_tokens`, `n_chars`
--
-- `n_tokens` = số token tách theo khoảng trắng trên văn bản ĐÃ LÀM SẠCH —
-- đúng cách RegexTokenizer của Task 7 tách từ, nên độ dài ở đây là độ dài mà
-- mô hình thực sự nhìn thấy. `n_chars` = số ký tự cùng văn bản đó.
-- Dùng PERCENTILE_APPROX (ước lượng) vì tính phân vị chính xác trên 129.701
-- dòng đắt hơn nhiều mà chỉ lệch dưới 1 token ở các mức đã kiểm tra.

SELECT
    label,
    count(*)                          AS n_comments,
    round(avg(n_tokens), 1)           AS mean_tokens,
    percentile_approx(n_tokens, 0.25) AS p25_tokens,
    percentile_approx(n_tokens, 0.50) AS p50_tokens,
    percentile_approx(n_tokens, 0.75) AS p75_tokens,
    percentile_approx(n_tokens, 0.95) AS p95_tokens,
    max(n_tokens)                     AS max_tokens,
    round(avg(n_chars), 1)            AS mean_chars,
    percentile_approx(n_chars, 0.50)  AS p50_chars
FROM train
GROUP BY label
ORDER BY label

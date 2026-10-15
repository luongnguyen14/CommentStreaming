-- q12_token_vocab.sql — Lượng hóa hạn chế của bước tách từ (KHÔNG có hình riêng)
--
-- Bảng ra : outputs/tables/eda_token_vocab.csv
-- Nguồn   : train (data/processed/train.parquet)
--
-- Câu hỏi: bộ tách từ của mô hình dùng RegexTokenizer với pattern "\s+" trên
-- văn bản đã làm sạch, mà bước làm sạch KHÔNG bỏ dấu câu ASCII. Hệ quả: "movie"
-- và "movie." (có dấu chấm) trở thành HAI từ khác nhau trong từ vựng. Truy vấn
-- này đo mức độ trùng lặp đó: đếm từ vựng thô so với từ vựng sau khi cắt dấu
-- câu ở hai đầu token.
--
-- Con số này dùng cho phần "hạn chế" của outputs/insights.md — cố tình KHÔNG
-- sửa bước tách từ ở Task 9, vì sửa nó là đổi đặc trưng của mô hình đã huấn
-- luyện (Task 7) và phải huấn luyện lại mới so sánh được.

WITH tokens AS (
    SELECT
        token AS token_raw,
        regexp_replace(token, '^[^\\p{L}\\p{N}<>]+|[^\\p{L}\\p{N}<>]+$', '') AS token_stripped
    FROM train
    LATERAL VIEW explode(split(text, ' ')) t AS token
)
SELECT
    count(*)                        AS n_token_occurrences,
    count(DISTINCT token_raw)       AS n_vocab_raw,
    count(DISTINCT token_stripped)  AS n_vocab_stripped,
    sum(CASE WHEN token_raw <> token_stripped THEN 1 ELSE 0 END)
                                    AS n_occurrences_with_edge_punct,
    round(100.0 * sum(CASE WHEN token_raw <> token_stripped THEN 1 ELSE 0 END)
          / count(*), 2)            AS pct_occurrences_with_edge_punct
FROM tokens

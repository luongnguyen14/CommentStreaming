-- q04_top_words_by_class.sql — Từ ĐẶC TRƯNG NHẤT của mỗi lớp cảm xúc (top {{top_words_n}})
--
-- Hình    : outputs/figures/08_top_words_by_class.png
-- Bảng ra : outputs/tables/eda_top_words_by_class.csv
-- Nguồn   : train (data/processed/train.parquet) + bảng tạm `stopwords`
--           (đúng danh sách StopWordsRemover mà Task 7 dùng, giữ lại từ phủ định)
--
-- Cách chọn "đặc trưng": log-odds có prior Dirichlet (Monroe, Colaresi & Quinn
-- 2008) của lớp đang xét so với HAI LỚP CÒN LẠI, chia cho độ lệch chuẩn để ra
-- z-score. Công thức:
--     alpha_w  = alpha_0 * (số lần từ w trong toàn bộ train) / (tổng số token)
--     log_odds = ln((y_c + alpha_w) / (n_c + alpha_0 - y_c - alpha_w))
--              - ln((y_o + alpha_w) / (n_o + alpha_0 - y_o - alpha_w))
--     z        = log_odds / sqrt(1/(y_c + alpha_w) + 1/(y_o + alpha_w))
-- trong đó y_c/n_c là số lần từ trong lớp đang xét và y_o/n_o là ở phần còn lại.
-- Prior giúp từ hiếm không chiếm bảng (từ chỉ xuất hiện 1 lần vẫn ra z rất cao
-- nếu không có prior), nên còn lọc thêm `n_in_class >= {{top_words_min_count}}`.
--
-- Đây là phân tích TẦN SUẤT (mô tả dữ liệu), khác với `outputs/tables/top_features.csv`
-- của Task 7 (trọng số học được của mô hình LogisticRegression). Hai bảng không
-- nhất thiết trùng nhau, và điều đó là bình thường.
--
-- Lưu ý: dấu câu dính ở hai đầu token được cắt cho dễ đọc
-- ("movie." -> "movie"). Bộ tách từ của mô hình KHÔNG cắt như vậy
-- (RegexTokenizer pattern \s+), tức mô hình coi "movie." và "movie" là hai từ
-- khác nhau — hạn chế được lượng hóa ở q12_token_vocab.sql.

WITH exploded AS (
    SELECT
        label,
        regexp_replace(token, '^[^\\p{L}\\p{N}<>]+|[^\\p{L}\\p{N}<>]+$', '') AS word
    FROM train
    LATERAL VIEW explode(split(text, ' ')) t AS token
),
words AS (
    SELECT label, word
    FROM exploded
    WHERE length(word) >= 2
      AND word NOT IN (SELECT w FROM stopwords)
),
per_class AS (
    SELECT label, word, count(*) AS n_in_class FROM words GROUP BY label, word
),
class_tot AS (SELECT label, sum(n_in_class) AS n_class FROM per_class GROUP BY label),
word_tot  AS (SELECT word, sum(n_in_class)  AS n_word  FROM per_class GROUP BY word),
tot       AS (SELECT sum(n_in_class) AS n_total FROM per_class),
base AS (
    SELECT p.label, p.word, p.n_in_class, c.n_class,
           (w.n_word - p.n_in_class)               AS n_in_other,
           (t.n_total - c.n_class)                 AS n_other_total,
           {{log_odds_prior}} * w.n_word / t.n_total AS alpha_w
    FROM per_class p
    JOIN class_tot c ON c.label = p.label
    JOIN word_tot  w ON w.word  = p.word
    CROSS JOIN tot t
),
scored AS (
    SELECT label, word, n_in_class,
           ln((n_in_class + alpha_w) / (n_class + {{log_odds_prior}} - n_in_class - alpha_w))
         - ln((n_in_other  + alpha_w) / (n_other_total + {{log_odds_prior}} - n_in_other - alpha_w)) AS log_odds,
           1.0 / (n_in_class + alpha_w) + 1.0 / (n_in_other + alpha_w)                                AS variance
    FROM base
),
ranked AS (
    SELECT label, word, n_in_class,
           round(log_odds, 4)                                  AS log_odds,
           round(log_odds / sqrt(variance), 2)                 AS z_score,
           row_number() OVER (PARTITION BY label
                              ORDER BY log_odds / sqrt(variance) DESC, word) AS rk
    FROM scored
    WHERE n_in_class >= {{top_words_min_count}}
)
SELECT label, rk, word, n_in_class, log_odds, z_score
FROM ranked
WHERE rk <= {{top_words_n}}
ORDER BY label, rk

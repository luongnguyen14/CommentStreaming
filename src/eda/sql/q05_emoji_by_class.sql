-- q05_emoji_by_class.sql — Emoji dùng nhiều nhất ở mỗi lớp cảm xúc
--
-- Hình    : outputs/figures/09_emoji_by_class.png
-- Bảng ra : outputs/tables/eda_emoji_by_class.csv
-- Nguồn   : train (data/processed/train.parquet)
--
-- Emoji đếm được vì bước 8 của src/common/text_cleaning.py đã TÁCH mỗi emoji
-- thành một token riêng ("hay👍quá" -> "hay 👍 quá"), nên chỉ cần explode theo
-- khoảng trắng rồi lọc token khớp lớp emoji.
--
-- Bộ lọc dùng HAI điều kiện, cả hai đều nhập từ text_cleaning.py (không chép lại):
--   (1) token RLIKE EMOJI_CLASS — đúng lớp mà bước làm sạch dùng để tách token
--       (lớp này KHÔNG gồm \p{Sk}, vì \p{Sk} bắt cả ký tự rác mã hóa "¨" U+00A8);
--   (2) token RLIKE dải emoji TƯỜNG MINH (EMOJI_SYMBOL_RANGES) — vì \p{So}
--       trong (1) bao gồm cả ký tự typography KHÔNG phải emoji: đo trên dữ liệu
--       thật thấy "°" (U+00B0) lọt vào top-30 emoji toàn bộ với 59 lần. Không có
--       (2) thì bảng "emoji theo lớp" sẽ có dòng "°" đứng đầu lớp negative.
-- Hệ quả: số emoji ở đây NHỎ HƠN hoặc bằng outputs/tables/emoji_frequency.csv
-- (bảng của Task 6 chỉ dùng điều kiện (1)).
--
-- Hai cách xếp hạng, đều có trong bảng ra:
--   rk_in_class — hạng trong lớp (dùng để biết lớp nào dùng emoji gì)
--   rk_global   — hạng trên toàn bộ train (dùng để chọn 12 emoji phổ biến nhất
--                 cho biểu đồ nhiệt; không có cột này thì mỗi lớp lấy 12 emoji
--                 khác nhau, không ghép lại thành một hình được)
-- Giữ dòng nếu nằm trong top `{{emoji_per_class_n}}` của lớp HOẶC của toàn bộ.
--
-- Chỉ số kèm theo mỗi lớp:
--   pct_comments_with_emoji = % bình luận CÓ ít nhất một emoji
--   emoji_per_1000_comments = số emoji trên 1.000 bình luận (mật độ dùng)
-- Hai chỉ số này khác nhau: một lớp có thể dùng ít emoji nhưng lặp lại nhiều.

WITH emoji_tokens AS (
    SELECT label, comment_id, token AS emoji
    FROM train
    LATERAL VIEW explode(split(text, ' ')) t AS token
    WHERE token RLIKE '{{emoji_class}}'
      AND token RLIKE '{{emoji_symbol_ranges}}'
),
per_comment AS (
    SELECT label, comment_id, count(*) AS n_emoji_in_comment
    FROM emoji_tokens
    GROUP BY label, comment_id
),
class_stats AS (
    SELECT
        t.label,
        count(*)                                AS n_comments_in_class,
        count(p.comment_id)                     AS n_comments_with_emoji,
        coalesce(sum(p.n_emoji_in_comment), 0)  AS n_emoji_in_class
    FROM train t
    LEFT JOIN per_comment p
           ON p.label = t.label AND p.comment_id = t.comment_id
    GROUP BY t.label
),
counts AS (
    SELECT label, emoji, count(*) AS n_emoji FROM emoji_tokens GROUP BY label, emoji
),
emoji_totals AS (
    SELECT emoji, sum(n_emoji) AS n_emoji_total FROM counts GROUP BY emoji
),
ranked AS (
    SELECT
        c.label, c.emoji, c.n_emoji, et.n_emoji_total,
        row_number()  OVER (PARTITION BY c.label ORDER BY c.n_emoji DESC, c.emoji)      AS rk_in_class,
        dense_rank()  OVER (ORDER BY et.n_emoji_total DESC, c.emoji)                    AS rk_global
    FROM counts c
    JOIN emoji_totals et ON et.emoji = c.emoji
)
SELECT
    r.label,
    r.rk_in_class,
    r.rk_global,
    r.emoji,
    r.n_emoji,
    r.n_emoji_total,
    s.n_comments_in_class,
    s.n_comments_with_emoji,
    round(100.0 * s.n_comments_with_emoji / s.n_comments_in_class, 2) AS pct_comments_with_emoji,
    round(1000.0 * s.n_emoji_in_class / s.n_comments_in_class, 1)     AS emoji_per_1000_comments,
    round(100.0 * r.n_emoji / s.n_emoji_in_class, 2)                  AS pct_of_class_emoji
FROM ranked r
JOIN class_stats s ON s.label = r.label
WHERE r.rk_in_class <= {{emoji_per_class_n}}
   OR r.rk_global   <= {{emoji_per_class_n}}
ORDER BY r.label, r.rk_in_class

-- q07_sentiment_per_10s.sql — Cảm xúc theo thời gian, cửa sổ TRƯỢT 10 giây (bước 5 giây)
--
-- Hình    : outputs/figures/10_sentiment_timeline.png (khung dưới)
-- Bảng ra : outputs/tables/eda_sentiment_per_10s.csv
-- Nguồn   : window_sliding_10s — đầu ra THẬT của query cửa sổ trượt trong
--           src/streaming/stream_job.py (window_duration 10 s, slide 5 s,
--           watermark 2 phút, chế độ append).
--
-- Vì sao cần thêm cửa sổ 10 giây bên cạnh cửa sổ 1 phút: lần chạy verify1 phát
-- 1.000 bình luận trong khoảng 10 giây, nên cửa sổ 1 phút chỉ có MỘT điểm dữ
-- liệu lớn — không thấy được diễn biến bên trong. Cửa sổ trượt 10 giây chia nhỏ
-- đúng khoảng thời gian đó. Lưu ý: các cửa sổ trượt CHỒNG NHAU nên KHÔNG được
-- cộng các dòng này lại để ra tổng số bình luận.

SELECT
    window_start,
    window_end,
    sum(n_comments)                                                   AS n_comments,
    sum(n_negative)                                                   AS n_negative,
    sum(n_neutral)                                                    AS n_neutral,
    sum(n_positive)                                                   AS n_positive,
    sum(CASE WHEN stream_id IN ({{synthetic_ids}}) THEN n_comments ELSE 0 END) AS n_synthetic,
    round(sum(n_negative) / sum(n_comments), 4)                       AS share_negative,
    round(sum(n_neutral)  / sum(n_comments), 4)                       AS share_neutral,
    round(sum(n_positive) / sum(n_comments), 4)                       AS share_positive
FROM window_sliding_10s
GROUP BY window_start, window_end
ORDER BY window_start

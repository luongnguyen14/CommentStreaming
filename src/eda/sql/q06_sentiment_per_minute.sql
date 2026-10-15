-- q06_sentiment_per_minute.sql — Cảm xúc theo thời gian, cửa sổ 1 phút (hình diện tích xếp chồng)
--
-- Hình    : outputs/figures/10_sentiment_timeline.png (khung trên)
-- Bảng ra : outputs/tables/eda_sentiment_per_minute.csv
-- Nguồn   : window_1min — đầu ra THẬT của query cửa sổ trong
--           src/streaming/stream_job.py (cửa sổ nhảy 1 phút, watermark 2 phút,
--           chế độ append), KHÔNG phải phép gộp lại từ bảng chi tiết.
--           Vì là đầu ra streaming nên cửa sổ chỉ được ghi SAU khi watermark
--           vượt qua cuối cửa sổ; các cửa sổ cuối còn nằm trong state lúc dừng
--           job sẽ không có trong bảng (đã nêu ở outputs/streaming_summary.md §6).
--
-- Bảng này gộp 3 lớp theo từng cửa sổ và TÁCH RIÊNG số bình luận đến từ
-- scripts/send_bad_events.py (`heartbeat`, `stream-test`) — đó là bản ghi kiểm
-- chứng, KHÔNG phải hành vi người xem. Phút nào chỉ toàn bản ghi kiểm chứng thì
-- tỷ lệ cảm xúc ở đó không có ý nghĩa (insights.md ghi rõ).

SELECT
    window_start,
    window_end,
    sum(n_comments)                                                   AS n_comments,
    sum(n_negative)                                                   AS n_negative,
    sum(n_neutral)                                                    AS n_neutral,
    sum(n_positive)                                                   AS n_positive,
    sum(CASE WHEN stream_id IN ({{synthetic_ids}}) THEN n_comments ELSE 0 END) AS n_synthetic,
    sum(CASE WHEN stream_id NOT IN ({{synthetic_ids}}) THEN n_comments ELSE 0 END) AS n_replay,
    round(sum(n_negative) / sum(n_comments), 4)                       AS share_negative,
    round(sum(n_neutral)  / sum(n_comments), 4)                       AS share_neutral,
    round(sum(n_positive) / sum(n_comments), 4)                       AS share_positive
FROM window_1min
GROUP BY window_start, window_end
ORDER BY window_start

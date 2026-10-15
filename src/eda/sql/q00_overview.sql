-- q00_overview.sql — Số kiểm tra nhanh trước khi phân tích (KHÔNG dùng để vẽ hình)
--
-- Mục đích: một dòng duy nhất ghi lại quy mô dữ liệu đã dùng cho EDA, để mọi
-- con số trong outputs/insights.md truy vết được về đúng bảng đã đọc.
-- Bảng nguồn: train, val, test (data/processed/*.parquet)
--             stream_detail, window_1min (đầu ra streaming của lần chạy verify1)
-- Bảng ra   : outputs/tables/eda_overview.csv
--
-- Lưu ý về thời gian: mọi mốc thời gian là UTC (cột event_time do producer sinh
-- theo ISO-8601 UTC; Spark session được đặt spark.sql.session.timeZone=UTC).

SELECT
    (SELECT count(*) FROM train)                    AS n_train,
    (SELECT count(*) FROM val)                      AS n_val,
    (SELECT count(*) FROM test)                     AS n_test,
    (SELECT count(DISTINCT stream_id) FROM train)   AS n_streams_train,
    (SELECT count(*) FROM stream_detail)            AS n_stream_comments,
    (SELECT count(DISTINCT stream_id) FROM stream_detail) AS n_streams_streaming,
    (SELECT min(event_time) FROM stream_detail)     AS stream_first_event_utc,
    (SELECT max(event_time) FROM stream_detail)     AS stream_last_event_utc,
    (SELECT count(*) FROM window_1min)              AS n_windows_1min_rows,
    (SELECT sum(n_comments) FROM window_1min)       AS n_comments_in_windows,
    -- Số bình luận đến từ script kiểm chứng (heartbeat / stream-test), tách khỏi
    -- dữ liệu replay thật để không đọc nhầm thành hành vi người xem.
    (SELECT count(*) FROM stream_detail
      WHERE stream_id IN ({{synthetic_ids}}))       AS n_synthetic_comments,
    (SELECT count(*) FROM stream_detail
      WHERE stream_id NOT IN ({{synthetic_ids}}))   AS n_replay_comments

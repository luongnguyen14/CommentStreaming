-- q01_class_distribution.sql — Phân bố nhãn cảm xúc của dữ liệu huấn luyện
--
-- Hình    : outputs/figures/06_class_distribution.png
-- Bảng ra : outputs/tables/eda_class_distribution.csv
-- Nguồn   : train / val / test (data/processed/*.parquet), cột `label`
--
-- Nhãn KHÔNG có sẵn trong bộ dữ liệu gốc: chúng được suy từ điểm `rating`
-- (1-4 negative, 5-6 neutral, 7-10 positive) theo quy ước ở config.yaml và
-- docs/data_dictionary.md §3. Vì vậy đây là phân bố của NHÃN THIẾT KẾ,
-- không phải nhãn do người gán cảm xúc.

WITH labeled AS (
    SELECT 'train' AS split, label FROM train
    UNION ALL
    SELECT 'val'   AS split, label FROM val
    UNION ALL
    SELECT 'test'  AS split, label FROM test
)
SELECT
    split,
    label,
    count(*)                                                     AS n_comments,
    round(count(*) / sum(count(*)) OVER (PARTITION BY split), 4)  AS share_in_split
FROM labeled
GROUP BY split, label
ORDER BY split, label

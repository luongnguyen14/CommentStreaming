# src/training — Chuẩn bị dữ liệu và huấn luyện

- `prepare.py` — nạp dữ liệu thô, chuẩn hóa nhãn, làm sạch, **loại trùng (kể cả gần trùng)**, chia train/val/test
- `train.py` — Spark ML Pipeline (RegexTokenizer -> StopWordsRemover -> n-gram -> CountVectorizer -> IDF -> classifier)

⚠️ TF-IDF nằm **trong Pipeline** để chỉ fit trên tập train. Tập test **chỉ dùng một lần** ở cuối.

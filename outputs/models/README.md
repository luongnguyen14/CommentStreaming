# outputs/models — Mô hình đã lưu

- `sentiment_pipeline/` — Spark `PipelineModel` tốt nhất (**Logistic Regression
  multinomial**, huấn luyện 15/10/2026), gồm cả TF-IDF đã fit **chỉ trên tập train**.
  Các tầng: RegexTokenizer → StopWordsRemover → NGram → CountVectorizer (20.000 từ) →
  IDF → Normalizer → LogisticRegression. Kích thước ~904 KB.
- `sentiment_pipeline_metadata.json` — ánh xạ nhãn (0/1/2 → negative/neutral/positive),
  tham số tốt nhất, phiên bản Spark (3.5.9), kích thước tập, ngày huấn luyện, chỉ số
  val/test.

**Cách dùng (Task 8 sẽ theo đúng đường đi này):**

```python
df = df.withColumn("text", clean_text(F.col("text")))   # src/common/text_cleaning.py
model = PipelineModel.load("file:///home/hadoop/capstone/outputs/models/sentiment_pipeline")
out = model.transform(df)      # cột `prediction` = 0/1/2 -> dịch bằng label_index
```

⚠️ **Văn bản phải được làm sạch bằng `src/common/text_cleaning.py` trước khi đưa vào
model** (cùng hàm dùng ở khâu huấn luyện — CLAUDE.md §4).

Kiểm chứng nhanh: `spark-submit scripts/check_model.py` (nạp lại model, dự đoán 5 câu thử).

Số liệu thật của mô hình này (test 27.792 dòng): accuracy 0,7018 · macro-F1 0,6233 ·
weighted F1 0,7213. Hạn chế đã biết: xem `outputs/modeling_summary.md` §5 và §8.

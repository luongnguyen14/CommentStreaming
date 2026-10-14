"""check_model.py — Nạp lại PipelineModel đã lưu và dự đoán thử vài câu.

Mục đích: kiểm chứng "đường đi" mà Task 8 (streaming) sẽ dùng — văn bản thô ->
`clean_text()` (dùng chung) -> `PipelineModel.transform()` -> chỉ số lớp -> tên lớp
theo `label_index` trong metadata. Chạy TRƯỚC khi dựng job streaming.

    source scripts/env.sh
    PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
        --driver-memory 2g --master 'local[2]' scripts/check_model.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyspark.ml import PipelineModel                              # noqa: E402
from pyspark.sql import SparkSession, functions as F              # noqa: E402

from src.common.text_cleaning import clean_text                   # noqa: E402
from src.common.utils import PROJECT_ROOT, load_config            # noqa: E402

TEST_SENTENCES = [
    "This movie was absolutely fantastic, I loved every minute of it!",
    "Boring, badly acted and way too long. I want my two hours back.",
    "It was okay, nothing special. 6/10",
    "not bad at all actually, quite enjoyable",
    "I have never laughed more, 10/10 would watch again",
]


def main() -> int:
    cfg = load_config()
    meta_path = Path(str(PROJECT_ROOT / cfg["training"]["model_out"]) + "_metadata.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    model_path = PROJECT_ROOT / cfg["training"]["model_out"]
    idx2lab = {int(v): k for k, v in meta["label_index"].items()}

    spark = (SparkSession.builder.appName("capstone-check-model").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    model = PipelineModel.load("file://" + str(model_path))
    print(f"Mô hình: {meta['model_name']} | lưu lúc {meta['saved_at']} | Spark {meta['spark_version']}")
    print(f"Nhãn: {idx2lab} | macro-F1 test: {meta['metrics']['test']['macro_f1']:.4f}")

    df = spark.createDataFrame([(t,) for t in TEST_SENTENCES], ["raw"])
    df = df.withColumn("text", clean_text(F.col("raw")))       # ĐÚNG hàm dùng chung
    for r in model.transform(df).select("raw", "text", "prediction", "probability").collect():
        probs = ", ".join(f"{idx2lab[i]}={p:.2f}" for i, p in enumerate(r["probability"]))
        print(f"  [{idx2lab[int(r['prediction'])]:8s}] {probs:48s} | sạch: {r['text'][:60]!r}")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

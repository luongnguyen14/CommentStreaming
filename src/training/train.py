"""train.py — Huấn luyện + đánh giá mô hình phân loại cảm xúc bằng Spark ML (Task 7).

Quy ước quan trọng (CLAUDE.md §6) — script này tuân thủ theo thứ tự sau:
  1. TF-IDF nằm TRONG Pipeline (RegexTokenizer -> StopWordsRemover -> NGram ->
     CountVectorizer -> IDF -> [Normalizer]) nên chỉ được học trên tập train.
  2. Chọn siêu tham số bằng TrainValidationSplit bên TRONG tập train — không
     bao giờ nhìn tập validation/test để chọn.
  3. So sánh các mô hình trên tập **validation**; chọn ra mô hình tốt nhất.
  4. Tập **test chỉ được dùng MỘT LẦN DUY NHẤT** ở cuối (đánh giá cuối cùng) và
     mọi lần dùng đều ghi vào `outputs/tables/test_eval_log.csv` để kiểm soát.
  5. Chỉ số báo cáo: accuracy, weighted F1, **macro-F1**, Precision/Recall/F1
     từng lớp — tất cả tính từ confusion matrix (dữ liệu mất cân bằng nên
     accuracy một mình gây hiểu nhầm).
  6. Nếu macro-F1 trên test cao bất thường (> ngưỡng trong config) -> dừng lại,
     kiểm tra trùng lặp/rò rỉ, KHÔNG lưu mô hình.

Chạy:
    source scripts/env.sh
    PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
        --driver-memory 2g --master 'local[2]' src/training/train.py --sample 20000 --no-test
    ... src/training/train.py          # bản đầy đủ (đánh giá test 1 lần)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pyspark.ml import Pipeline                           # noqa: E402
from pyspark.ml.classification import (                    # noqa: E402
    LinearSVC,
    LogisticRegression,
    NaiveBayes,
    OneVsRest,
    RandomForestClassifier,
)
from pyspark.ml.evaluation import MulticlassClassificationEvaluator  # noqa: E402
from pyspark.ml.feature import (                            # noqa: E402
    CountVectorizer,
    IDF,
    NGram,
    Normalizer,
    RegexTokenizer,
    StopWordsRemover,
)
from pyspark.ml.functions import vector_to_array           # noqa: E402
from pyspark.ml.tuning import TrainValidationSplit         # noqa: E402
from pyspark.sql import SparkSession, functions as F       # noqa: E402

from src.common.metrics import confusion_matrix, metrics_from_cm  # noqa: E402
from src.common.plotting import SENTIMENT_COLORS, apply_style, save_fig  # noqa: E402
from src.common.text_cleaning import dedup_key             # noqa: E402
from src.common.utils import PROJECT_ROOT, load_config     # noqa: E402

LABEL_COL = "label_idx"
WEIGHT_COL = "weight"
FEATURES_COL = "features"
PRED_COL = "pred_idx"

# Tên hiển thị của mô hình (dùng trong bảng/biểu đồ)
MODEL_NAMES = {
    "baseline": "MajorityBaseline",
    "nb": "NaiveBayes",
    "lr": "LogisticRegression",
    "svc": "LinearSVC(OvR)",
    "rf": "RandomForest",
}

# Nhóm nguyên nhân trong error_analysis.csv viết tiếng Việt; khi VẼ HÌNH thì dịch
# sang tiếng Anh cho đúng quy ước "chữ trong hình là tiếng Anh" (CLAUDE.md §8).
REASON_EN = {
    "nghi mỉa mai (cần đọc tay)": "sarcasm (suspected)",
    "nhãn neutral nhiễu (suy từ rating 5-6)": "noisy neutral label (rating 5-6)",
    "phủ định (not/never...)": "negation (not/never)",
    "có ý trái chiều (but/however)": "contrasting opinion (but/however)",
    "quá ngắn, ít thông tin": "too short / little information",
    "có <url>/<user>, thiếu ngữ cảnh": "URL/user token, missing context",
    "khác (cần đọc tay)": "other (needs manual reading)",
}

# --- Tiện ích nhỏ -----------------------------------------------------------

def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def local_uri(path: str | Path) -> str:
    """HDFS là filesystem mặc định của Spark ở máy này -> đường dẫn cục bộ phải
    ghi rõ `file://`, nếu không Spark đi tìm trên HDFS (đã gặp thật ở Task 6)."""
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return "file://" + str(p)


def fmt_params(pmap: dict) -> str:
    """ParamMap -> chuỗi ngắn gọn để ghi vào bảng kết quả."""
    return ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                     for k, v in sorted(pmap.items()))


# --- Chỉ số: TÍNH TỪ CONFUSION MATRIX --------------------------------------
# `confusion_matrix` và `metrics_from_cm` nằm ở src/common/metrics.py để
# chương trình thử nghiệm (src/app/model_trial.py) dùng ĐÚNG công thức này.


def with_argmax_prediction(df, raw_col: str = "rawPrediction", out_col: str = PRED_COL):
    """Thêm cột dự đoán = argmax(rawPrediction), viết bằng hàm Spark SQL (không UDF).

    Dùng cho LinearSVC: `one-vs-rest` trả về điểm lề (margin) chứ không phải xác
    suất, nên ngưỡng 0.5 của OneVsRest là vô nghĩa — lấy lớp có điểm cao nhất.
    (array_position nhận tham số thứ hai là BIỂU THỨC nên phải viết bằng SQL.)
    """
    tmp = "_raw_arr"
    df = df.withColumn(tmp, vector_to_array(F.col(raw_col)))
    return df.withColumn(
        out_col, F.expr(f"array_position({tmp}, array_max({tmp})) - 1").cast("double")
    ).drop(tmp)


# --- Chuẩn bị dữ liệu -------------------------------------------------------

def add_label_index(df, label_index: dict[str, int]):
    """Nhãn chuỗi -> chỉ số số (0/1/2) theo `labels.index` trong config.yaml."""
    expr = F.lit(-1.0)
    for lab, idx in sorted(label_index.items(), key=lambda kv: kv[1]):
        expr = F.when(F.col("label") == lab, F.lit(float(idx))).otherwise(expr)
    return df.withColumn(LABEL_COL, expr)


def add_class_weights(df, weight_name: str = WEIGHT_COL):
    """Trọng số theo lớp w_c = N / (k * n_c) — tính TRÊN TẬP TRAIN.

    Dữ liệu lệch (positive 61%, neutral 14%): không cân bằng thì mô hình thiên
    hẳn về lớp đa số và lớp neutral gần như bị bỏ.
    """
    counts = {int(r[LABEL_COL]): r["count"] for r in df.groupBy(LABEL_COL).count().collect()}
    total = sum(counts.values())
    k = len(counts)
    weights = {lab: total / (k * n) for lab, n in counts.items()}
    expr = F.lit(1.0)
    for lab, w in sorted(weights.items()):
        expr = F.when(F.col(LABEL_COL) == float(lab), F.lit(float(w))).otherwise(expr)
    log("Trọng số lớp (tính trên tập train): "
        + ", ".join(f"lớp {lab}: {w:.3f} (n={counts[lab]:,})" for lab, w in sorted(weights.items())))
    return df.withColumn(weight_name, expr)


def leak_audit(tr, va, te, out_path: Path) -> dict:
    """Kiểm tra rò rỉ: có văn bản nào xuất hiện ở cả hai tập không?

    Vì prepare.py đã loại trùng trước khi chia, con số kỳ vọng là 0. Nếu khác 0
    thì mọi chỉ số đều đáng ngờ (CLAUDE.md §6).
    """
    keys_tr = tr.withColumn("_k", dedup_key(F.col("text"))).select("_k")
    keys_va = va.withColumn("_k", dedup_key(F.col("text"))).select("_k")
    keys_te = (None if te is None
               else te.withColumn("_k", dedup_key(F.col("text"))).select("_k"))
    n_tv = keys_tr.join(keys_va, "_k").count()
    n_tt = keys_tr.join(keys_te, "_k").count() if keys_te is not None else None
    n_vt = keys_va.join(keys_te, "_k").count() if keys_te is not None else None
    info = {"trung_van_ban_train_val": n_tv, "trung_van_ban_train_test": n_tt,
            "trung_van_ban_val_test": n_vt, "checked_at": datetime.now().isoformat(timespec="seconds")}
    log(f"Kiểm tra rò rỉ (trùng văn bản sau chuẩn hóa): train↔val {n_tv} | "
        f"train↔test {n_tt} | val↔test {n_vt}")
    out_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


# --- Pipeline ---------------------------------------------------------------

def build_stopwords(tcfg: dict) -> list[str]:
    sw = list(StopWordsRemover.loadDefaultStopWords("english"))
    if tcfg.get("keep_negations", True):
        # Lấy lại các từ phủ định khỏi danh sách stopword của Spark.
        keep = {"not", "no", "nor", "never", "none", "cannot",
                "couldn't", "didn't", "doesn't", "don't", "hadn't", "hasn't",
                "haven't", "isn't", "mightn't", "mustn't", "needn't", "shan't",
                "shouldn't", "wasn't", "weren't", "won't", "wouldn't", "ain't"}
        sw = [w for w in sw if w not in keep]
    sw = sorted(set(sw) | set(tcfg.get("stopwords_extra") or []))
    log(f"Stopword: {len(sw)} từ (giữ phủ định: {tcfg.get('keep_negations', True)})")
    return sw


def build_pipeline(name: str, tcfg: dict, stopwords: list[str], params: dict, seed: int) -> Pipeline:
    """Pipeline dùng chung cho mọi mô hình: văn bản -> đặc trưng -> bộ phân loại.

    `params` là một tổ hợp siêu tham số (ngram, vocab_size, ...) lấy từ lưới.
    """
    vec = tcfg["vectorizer"]
    ngram = int(params.get("ngram", 1))
    vocab = int(params.get("vocab_size", vec["vocab_size"]))
    stages = [
        RegexTokenizer(inputCol="text", outputCol="tokens", pattern=r"\s+",
                       minTokenLength=1, toLowercase=False),   # text đã lower ở khâu làm sạch
        StopWordsRemover(inputCol="tokens", outputCol="words",
                         stopWords=stopwords, caseSensitive=False),
        NGram(inputCol="words", outputCol="ngrams", n=ngram),
        CountVectorizer(inputCol="ngrams", outputCol="tf",
                        vocabSize=vocab, minDF=float(vec["min_df"])),
        IDF(inputCol="tf", outputCol="tfidf"),
    ]
    if tcfg.get("normalize_l2", True):
        stages.append(Normalizer(inputCol="tfidf", outputCol=FEATURES_COL, p=2.0))
        feat = FEATURES_COL
    else:
        feat = "tfidf"

    common = dict(featuresCol=feat, labelCol=LABEL_COL, weightCol=WEIGHT_COL)
    if name == "nb":
        clf = NaiveBayes(modelType="multinomial", smoothing=float(params.get("smoothing", 1.0)), **common)
    elif name == "lr":
        clf = LogisticRegression(
            family="multinomial",
            regParam=float(params.get("reg_param", 0.0)),
            elasticNetParam=float(params.get("elastic_net", 0.0)),
            maxIter=int(params.get("max_iter", 20)),
            **common,
        )
    elif name == "svc":
        base = LinearSVC(regParam=float(params.get("reg_param", 0.01)),
                         maxIter=int(params.get("max_iter", 20)),
                         standardization=True, **common)
        clf = OneVsRest(classifier=base, parallelism=1,
                        **{k: v for k, v in common.items() if k != "weightCol"},
                        weightCol=WEIGHT_COL)
    elif name == "rf":
        clf = RandomForestClassifier(
            numTrees=int(params.get("num_trees", 30)),
            maxDepth=int(params.get("max_depth", 8)),
            seed=seed, maxBins=32, **common,
        )
    else:
        raise ValueError(f"Mô hình không hỗ trợ: {name}")
    return Pipeline(stages=stages + [clf])


def grid_param_objects(pipeline: Pipeline, name: str) -> dict:
    """Ánh xạ tên tham số trong config -> đối tượng Param của Spark (để build lưới)."""
    st = pipeline.getStages()
    ng, cv, clf = st[2], st[3], st[-1]
    objs = {"ngram": ng.n, "vocab_size": cv.vocabSize}
    if name == "nb":
        objs["smoothing"] = clf.smoothing
    elif name == "lr":
        objs.update(reg_param=clf.regParam, elastic_net=clf.elasticNetParam, max_iter=clf.maxIter)
    elif name == "svc":
        inner = clf.getClassifier()
        objs.update(reg_param=inner.regParam, max_iter=inner.maxIter)
    elif name == "rf":
        objs.update(num_trees=clf.numTrees, max_depth=clf.maxDepth)
    return objs


def build_param_maps(grid_cfg: dict, objs: dict) -> list[dict]:
    """Tích Descartes của lưới trong config -> danh sách ParamMap cho TVS."""
    keys = list(grid_cfg.keys())
    unknown = [k for k in keys if k not in objs]
    if unknown:
        raise ValueError(f"Tham số không có trong pipeline: {unknown}")
    values = [grid_cfg[k] if isinstance(grid_cfg[k], list) else [grid_cfg[k]] for k in keys]
    return [dict(zip((objs[k] for k in keys), combo)) for combo in product(*values)]


# --- Huấn luyện + đánh giá một mô hình -------------------------------------

def predict_to_pandas(model, df, name: str) -> tuple["object", float]:
    """Dự đoán + đo THỜI GIAN dự đoán (gồm cả bước vector hóa).

    LinearSVC: `prediction` của OneVsRest dựa trên ngưỡng nên không đáng tin với
    điểm lề (margin) chứ không phải xác suất; dùng argmax(rawPrediction) và đo
    luôn mức khớp giữa hai cách để báo cáo trung thực.
    """
    out = model.transform(df)
    if name == "svc":
        out = with_argmax_prediction(out)
    else:
        out = out.withColumn(PRED_COL, F.col("prediction"))
    cols = ["comment_id", "text", "n_chars", "n_tokens", LABEL_COL, PRED_COL]
    if name == "svc":
        cols.append("prediction")               # giữ lại để so sánh trong pandas
    if "probability" in out.columns:
        prob = vector_to_array(F.col("probability"))
        out = out.withColumn("_p_true", F.element_at(prob, (F.col(LABEL_COL) + 1).cast("int")))
        cols.append("_p_true")
    t0 = time.time()
    pdf = out.select(*cols).toPandas()          # kéo hết về driver -> đo trọn vẹn
    seconds = time.time() - t0
    pdf[LABEL_COL] = pdf[LABEL_COL].astype(int)
    pdf[PRED_COL] = pdf[PRED_COL].astype(int)
    if name == "svc":
        same = float((pdf["prediction"].astype(int) == pdf[PRED_COL]).mean())
        log(f"  SVC: prediction của OneVsRest khớp argmax(rawPrediction) ở {same:.2%} dòng "
            f"-> dùng argmax")
        pdf = pdf.drop(columns=["prediction"])
    return pdf, seconds


def run_model(name: str, tr, va, tcfg: dict, stopwords: list[str], seed: int,
              labels: list[str]) -> dict:
    """TVS chọn siêu tham số trên train -> đánh giá trên val. Trả về kết quả."""
    grid_cfg = tcfg["grids"][name]
    keys = list(grid_cfg.keys())
    values = [grid_cfg[k] if isinstance(grid_cfg[k], list) else [grid_cfg[k]] for k in keys]
    combos = [dict(zip(keys, c)) for c in product(*values)]
    log(f"== {MODEL_NAMES[name]}: {len(combos)} tổ hợp siêu tham số ==")
    for c in combos:
        log(f"   - {c}")

    pipeline = build_pipeline(name, tcfg, stopwords, combos[0] if combos else {}, seed)
    param_maps = build_param_maps(grid_cfg, grid_param_objects(pipeline, name))
    evaluator = MulticlassClassificationEvaluator(
        labelCol=LABEL_COL, predictionCol="prediction", metricName=tcfg["tvs"]["metric"])
    tvs = TrainValidationSplit(estimator=pipeline, estimatorParamMaps=param_maps,
                               evaluator=evaluator, trainRatio=float(tcfg["tvs"]["train_ratio"]),
                               seed=seed, collectSubModels=False)
    t0 = time.time()
    model = tvs.fit(tr)          # chọn tổ hợp tốt nhất rồi fit lại trên TOÀN BỘ train
    train_s = time.time() - t0

    best_i = int(np.argmax(model.validationMetrics))
    best_map = {p.name: v for p, v in model.getEstimatorParamMaps()[best_i].items()}
    best_score = float(model.validationMetrics[best_i])
    log(f"  TVS xong sau {train_s:.0f}s | tốt nhất: {fmt_params(best_map)} "
        f"(weighted F1 nội bộ {best_score:.4f})")

    pdf, pred_s = predict_to_pandas(model, va, name)
    n_bad = int(((pdf[PRED_COL] < 0) | (pdf[PRED_COL] >= len(labels))).sum())
    if n_bad:
        log(f"  ! {n_bad} dòng có chỉ số dự đoán ngoài khoảng lớp — gán về lớp 0 (cần kiểm tra)")
        pdf[PRED_COL] = pdf[PRED_COL].clip(0, len(labels) - 1)
    cm = confusion_matrix(pdf[LABEL_COL].values, pdf[PRED_COL].values, len(labels))
    overall, per_class = metrics_from_cm(cm, labels)
    log(f"  Trên VALIDATION: acc {overall['accuracy']:.4f} | macro-F1 {overall['macro_f1']:.4f} | "
        f"weighted-F1 {overall['weighted_f1']:.4f} | dự đoán {pred_s:.1f}s cho {len(pdf):,} dòng")
    return {
        "name": name, "model": model, "best_model": model.bestModel, "params": best_map,
        "tvs_score": best_score, "n_candidates": len(combos), "train_seconds": train_s,
        "predict_seconds": pred_s, "pdf": pdf, "cm": cm, "metrics": overall,
        "per_class": per_class,
        "n_features": len(model.bestModel.stages[3].vocabulary),   # CountVectorizerModel
    }


def run_baseline(tr, va, labels: list[str]) -> dict:
    """Baseline đa số: luôn đoán lớp phổ biến nhất của tập train."""
    major = int(tr.groupBy(LABEL_COL).count().orderBy(F.desc("count")).first()[0])
    log(f"== {MODEL_NAMES['baseline']}: luôn đoán lớp {labels[major]} ==")
    pdf = (va.withColumn(PRED_COL, F.lit(float(major)))
             .select("comment_id", "text", "n_chars", "n_tokens", LABEL_COL, PRED_COL)
             .toPandas())
    pdf[LABEL_COL] = pdf[LABEL_COL].astype(int)
    pdf[PRED_COL] = pdf[PRED_COL].astype(int)
    cm = confusion_matrix(pdf[LABEL_COL].values, pdf[PRED_COL].values, len(labels))
    overall, per_class = metrics_from_cm(cm, labels)
    log(f"  Trên VALIDATION: acc {overall['accuracy']:.4f} | macro-F1 {overall['macro_f1']:.4f}")
    return {"name": "baseline", "model": None, "best_model": None, "params": {"majority": labels[major]},
            "tvs_score": float("nan"), "n_candidates": 0, "train_seconds": 0.0,
            "predict_seconds": 0.0, "pdf": pdf, "cm": cm, "metrics": overall,
            "per_class": per_class, "n_features": 0}


# --- Trích trọng số từ (mô hình tuyến tính) --------------------------------

def extract_weights(result: dict, name: str):
    """Trả về (vocab, ma trận trọng số [lớp x từ]) của mô hình tuyến tính."""
    pm = result["best_model"]
    vocab = list(pm.stages[3].vocabulary)
    clf = pm.stages[-1]
    if name == "lr":
        mat = np.array(clf.coefficientMatrix.toArray())          # (numClasses, numFeatures)
    elif name == "svc":
        mat = np.array([m.coefficients.toArray() for m in clf.models])
    elif name == "nb":
        mat = np.array(clf.theta.toArray())                      # log xác suất (không phải hệ số)
    else:
        return None, None
    if mat.shape[1] != len(vocab):        # phòng khi vocab bị cắt khác số đặc trưng
        n = min(mat.shape[1], len(vocab))
        mat, vocab = mat[:, :n], vocab[:n]
    return vocab, mat


def top_features_table(result: dict, name: str, labels: list[str], top_n: int) -> "object":
    import pandas as pd

    vocab, mat = extract_weights(result, name)
    if vocab is None:
        return None
    rows = []
    for i, lab in enumerate(labels):
        order = np.argsort(-mat[i])[:top_n]
        for rank, j in enumerate(order, start=1):
            rows.append({"model": MODEL_NAMES[name], "label": lab, "rank": rank,
                         "feature": vocab[j], "weight": float(mat[i, j])})
    return pd.DataFrame(rows)


# --- Phân tích lỗi ----------------------------------------------------------

def error_analysis(pdf, labels: list[str], rules: dict, n: int) -> "object":
    """Lấy n bình luận dự đoán sai (ẩn danh: bỏ user_hash), gán nhóm nguyên nhân.

    Quy tắc gán nhóm là suy đoán từ khoá/độ dài — chỉ để CHIA NHÓM ban đầu cho
    người đọc rà lại, không phải kết luận. Thứ tự ưu tiên ghi rõ trong code.
    """
    wrong = pdf[pdf[LABEL_COL] != pdf[PRED_COL]].copy()
    if wrong.empty:
        return None
    wrong["_h"] = [zlib.crc32(str(c).encode("utf-8")) for c in wrong["comment_id"]]
    wrong = wrong.sort_values("_h").head(n)

    def reason(text: str, true_lab: str, n_chars: int) -> str:
        """Gán nhóm nguyên nhân theo thứ tự ưu tiên (chỉ là gợi ý chia nhóm)."""
        t = " " + str(text).lower() + " "
        if any(m in t for m in rules["sarcasm_markers"]):
            return "nghi mỉa mai (cần đọc tay)"
        if true_lab == "neutral":
            return "nhãn neutral nhiễu (suy từ rating 5-6)"
        if "n't" in t or any(f" {m} " in t for m in rules["negation_markers"]):
            return "phủ định (not/never...)"
        if any(f" {m} " in t for m in rules["contrast_markers"]):
            return "có ý trái chiều (but/however)"
        if n_chars < rules["short_chars"]:
            return "quá ngắn, ít thông tin"
        if "<url>" in t or "<user>" in t:
            return "có <url>/<user>, thiếu ngữ cảnh"
        return "khác (cần đọc tay)"

    out = wrong.assign(
        reason=[reason(t, labels[a], c) for t, a, c in
                zip(wrong["text"], wrong[LABEL_COL], wrong["n_chars"])],
        true_label=[labels[a] for a in wrong[LABEL_COL]],
        pred_label=[labels[p] for p in wrong[PRED_COL]],
    )
    cols = ["comment_id", "true_label", "pred_label"] + \
           (["_p_true"] if "_p_true" in out.columns else []) + \
           ["n_chars", "n_tokens", "reason", "text"]
    return out[cols]


# --- Biểu đồ ----------------------------------------------------------------

def plot_confusion(cm: np.ndarray, labels: list[str], path: Path, note: str, title: str):
    import matplotlib.pyplot as plt

    row_norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    im = ax.imshow(row_norm, cmap="Blues", vmin=0, vmax=1)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{row_norm[i, j]:.2f}\n({cm[i, j]:,})", ha="center", va="center",
                    fontsize=9, color="white" if row_norm[i, j] > 0.55 else "#222222")
    ax.set_xticks(range(len(labels)), labels)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(title)
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.046, label="Share of true class")
    fig.subplots_adjust(bottom=0.20)          # chừa chỗ cho dòng ghi chú nguồn
    save_fig(fig, path, note=note)
    plt.close(fig)


def plot_per_class(per_class: dict, labels: list[str], path: Path, note: str, title: str):
    import matplotlib.pyplot as plt

    metrics = ["precision", "recall", "f1"]
    colors = {"precision": "#264653", "recall": "#457B9D", "f1": "#E9C46A"}
    x = np.arange(len(labels))
    w = 0.26
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for k, m in enumerate(metrics):
        vals = [per_class[lab][m] for lab in labels]
        bars = ax.bar(x + (k - 1) * w, vals, w, label=m.capitalize(), color=colors[m],
                      edgecolor="white")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.2f}",
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Score (0-1)")
    ax.set_title(title)
    ax.legend(ncol=3, frameon=False, loc="upper center")
    fig.subplots_adjust(bottom=0.22)          # chừa chỗ cho dòng ghi chú nguồn
    save_fig(fig, path, note=note)
    plt.close(fig)


def plot_model_comparison(rows: list[dict], path: Path, note: str):
    import matplotlib.pyplot as plt

    rows = [r for r in rows if r["split"] == "val"]
    rows = sorted(rows, key=lambda r: r["macro_f1"])
    names = [r["model"] for r in rows]
    vals = [r["macro_f1"] for r in rows]
    fig, ax = plt.subplots(figsize=(6.6, 0.7 + 0.5 * len(rows)))
    colors = ["#9A9A9A" if n == MODEL_NAMES["baseline"] else "#457B9D" for n in names]
    bars = ax.barh(names, vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(v + 0.008, b.get_y() + b.get_height() / 2, f"{v:.3f}", va="center", fontsize=9)
    ax.set_xlim(0, max(vals) * 1.18 if vals else 1)
    ax.set_xlabel("Macro-F1 on validation set (0-1)")
    ax.set_title("Model comparison (validation set)")
    fig.subplots_adjust(bottom=0.24)          # chừa chỗ cho dòng ghi chú nguồn
    save_fig(fig, path, note=note)
    plt.close(fig)


def plot_top_features(df_top, labels: list[str], path: Path, note: str, model_label: str):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(labels), figsize=(4.2 * len(labels), 6.4))
    for ax, lab in zip(np.atleast_1d(axes), labels):
        sub = df_top[df_top["label"] == lab].sort_values("weight")
        ax.barh(sub["feature"], sub["weight"], color=SENTIMENT_COLORS[lab])
        ax.set_title(f"{lab} — top {len(sub)}")
        ax.set_xlabel("Feature weight")
        ax.tick_params(axis="y", labelsize=8)
    fig.suptitle(f"Top weighted features per class ({model_label})", y=0.99)
    save_fig(fig, path, note=note)
    plt.close(fig)


def plot_error_reasons(df_err, path: Path, note: str):
    import matplotlib.pyplot as plt

    # Nhãn trong hình phải là tiếng Anh (CLAUDE.md §8); CSV giữ nguyên tiếng Việt.
    counts = df_err["reason"].map(lambda r: REASON_EN.get(r, r)).value_counts()
    fig, ax = plt.subplots(figsize=(7.2, 0.9 + 0.5 * len(counts)))
    bars = ax.barh(counts.index[::-1], counts.values[::-1], color="#E76F51")
    for b, v in zip(bars, counts.values[::-1]):
        ax.text(v + 0.1, b.get_y() + b.get_height() / 2, f"{int(v)}", va="center", fontsize=9)
    ax.set_xlabel("Number of misclassified comments (count)")
    ax.set_title(f"Error analysis: {int(counts.sum())} misclassified comments by cause")
    ax.set_xlim(0, counts.max() * 1.2)
    fig.subplots_adjust(bottom=0.28)          # chừa chỗ cho dòng ghi chú nguồn
    save_fig(fig, path, note=note)
    plt.close(fig)


# --- Chương trình chính -----------------------------------------------------

def figures_only(cfg: dict) -> int:
    """Vẽ lại TOÀN BỘ hình từ các bảng CSV đã lưu (không huấn luyện, không chạm test).

    Nhờ vậy sửa bố cục hình không phải chạy lại mô hình — và cũng không "dùng" tập
    test lần thứ hai (mọi số liệu đã nằm trong outputs/tables/).
    """
    import pandas as pd

    tables = PROJECT_ROOT / cfg["paths"]["outputs_tables"]
    figures = PROJECT_ROOT / cfg["paths"]["outputs_figures"]
    labels = [lab for lab, _ in sorted(cfg["labels"]["index"].items(), key=lambda kv: kv[1])]
    apply_style()

    cm_df = pd.read_csv(tables / "confusion_matrix.csv")
    model_name = cm_df["model"].iloc[0]
    split = cm_df["split"].iloc[0]
    cm = (cm_df.pivot(index="true_label", columns="pred_label", values="count")
              .reindex(index=labels, columns=labels).fillna(0).values.astype(int))
    note = f"Source: outputs/tables/confusion_matrix.csv — {model_name} on {split} (Task 7)"
    plot_confusion(cm, labels, figures / "01_confusion_matrix.png", note,
                   f"Confusion matrix (row-normalized) — {model_name}, {split}")

    pc_df = pd.read_csv(tables / "per_class_metrics.csv")
    pc_df = pc_df[(pc_df["model"] == model_name) & (pc_df["split"] == split)]
    per_class = {r["label"]: {"precision": r["precision"], "recall": r["recall"],
                              "f1": r["f1"], "support": int(r["support"])}
                 for _, r in pc_df.iterrows()}
    plot_per_class(per_class, labels, figures / "02_per_class_prf1.png",
                   f"Source: outputs/tables/per_class_metrics.csv — {model_name} on {split}",
                   f"Precision / Recall / F1 by class — {model_name}, {split}")

    plot_model_comparison(pd.read_csv(tables / "model_results.csv").to_dict("records"),
                          figures / "03_model_comparison.png",
                          "Source: outputs/tables/model_results.csv (validation set)")

    top_path = tables / "top_features.csv"
    if top_path.exists():
        df_top = pd.read_csv(top_path)
        plot_top_features(df_top, labels, figures / "04_top_features.png",
                          f"Source: outputs/tables/top_features.csv — {df_top['model'].iloc[0]}",
                          df_top["model"].iloc[0])

    err_path = tables / "error_analysis.csv"
    if err_path.exists():
        plot_error_reasons(pd.read_csv(err_path), figures / "05_error_reasons.png",
                           "Source: outputs/tables/error_analysis.csv")
    log("Đã vẽ lại hình từ outputs/tables/ (không huấn luyện lại, không chạm tập test).")
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Huấn luyện + đánh giá mô hình cảm xúc (Task 7)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--sample", type=int, default=None,
                    help="chạy thử với ~N dòng train (tất định theo crc32)")
    ap.add_argument("--models", default="nb,lr,svc,rf", help="danh sách mô hình, ví dụ nb,lr")
    ap.add_argument("--no-test", action="store_true", help="KHÔNG đánh giá tập test (chạy thử)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--figures-only", action="store_true",
                    help="chỉ vẽ lại hình từ outputs/tables/*.csv, không huấn luyện")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    tcfg = cfg["training"]
    if args.figures_only:
        return figures_only(cfg)
    if args.sample:
        # Chạy thử thì KHÔNG được chạm vào tập test (CLAUDE.md §6)
        args.no_test = True
    seed = args.seed if args.seed is not None else cfg["seed"]
    labels = [lab for lab, _ in sorted(cfg["labels"]["index"].items(), key=lambda kv: kv[1])]
    label_index = cfg["labels"]["index"]
    tables_dir = PROJECT_ROOT / cfg["paths"]["outputs_tables"]
    figures_dir = PROJECT_ROOT / cfg["paths"]["outputs_figures"]
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    spark = (SparkSession.builder
             .appName("capstone-task7-train")
             .config("spark.sql.shuffle.partitions", "8")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    log(f"Spark {spark.version} | seed {seed} | mô hình: {args.models}"
        + (" | CHẾ ĐỘ CHẠY THỬ" if args.sample else ""))

    # --- 1. Nạp dữ liệu -----------------------------------------------------
    tr = add_label_index(spark.read.parquet(local_uri(cfg["paths"]["train"])), label_index)
    va = add_label_index(spark.read.parquet(local_uri(cfg["paths"]["val"])), label_index)
    te = None if args.no_test else add_label_index(
        spark.read.parquet(local_uri(cfg["paths"]["test"])), label_index)
    if args.sample:
        tr = tr.orderBy(F.crc32(F.col("comment_id"))).limit(args.sample)
        va = va.orderBy(F.crc32(F.col("comment_id"))).limit(max(args.sample // 5, 2000))
    tr = tr.cache()
    va = va.cache()
    log(f"Dữ liệu: train {tr.count():,} | val {va.count():,} | test "
        + (f"{te.count():,}" if te is not None else "(bỏ qua)"))

    # --- 2. Trọng số lớp + kiểm tra rò rỉ -----------------------------------
    tr = add_class_weights(tr)
    audit = leak_audit(tr, va, te, tables_dir / "leak_check.json")

    # --- 3. Huấn luyện từng mô hình, đánh giá trên VALIDATION ---------------
    stopwords = build_stopwords(tcfg)
    results, val_rows, per_class_rows = [], [], []
    baseline = run_baseline(tr, va, labels)
    results.append(baseline)
    for r, pc in [(baseline["metrics"], baseline["per_class"])]:
        val_rows.append(dict(model=MODEL_NAMES["baseline"], split="val", **{
            k: r[k] for k in ("accuracy", "weighted_f1", "macro_f1", "macro_precision", "macro_recall", "n")},
            best_params="majority=" + baseline["params"]["majority"], n_candidates=0,
            n_features=0, train_seconds=0.0, predict_seconds_per_10k=0.0))
        for lab in labels:
            per_class_rows.append(dict(model=MODEL_NAMES["baseline"], split="val", label=lab, **pc[lab]))

    for name in [m.strip() for m in args.models.split(",") if m.strip()]:
        res = run_model(name, tr, va, tcfg, stopwords, seed, labels)
        results.append(res)
        r = res["metrics"]
        val_rows.append(dict(
            model=MODEL_NAMES[name], split="val",
            **{k: r[k] for k in ("accuracy", "weighted_f1", "macro_f1", "macro_precision",
                                 "macro_recall", "n")},
            best_params=fmt_params(res["params"]), n_candidates=res["n_candidates"],
            n_features=res["n_features"], train_seconds=round(res["train_seconds"], 1),
            predict_seconds_per_10k=round(res["predict_seconds"] / max(len(res["pdf"]), 1) * 10000, 2)))
        for lab in labels:
            per_class_rows.append(dict(model=MODEL_NAMES[name], split="val",
                                       label=lab, **res["per_class"][lab]))

    # --- 4. Chọn mô hình tốt nhất trên VALIDATION ---------------------------
    trained = [r for r in results if r["name"] != "baseline"]
    best = max(trained, key=lambda r: r["metrics"]["macro_f1"])
    log("Xếp hạng trên validation (macro-F1): "
        + " | ".join(f"{MODEL_NAMES[r['name']]} {r['metrics']['macro_f1']:.4f}"
                     for r in sorted(results, key=lambda x: -x["metrics"]["macro_f1"])))
    log(f"Mô hình chọn: {MODEL_NAMES[best['name']]} ({fmt_params(best['params'])})")

    # --- 5. Đánh giá CUỐI CÙNG trên test (một lần duy nhất) -----------------
    test_rows, test_cm, test_per_class, test_pdf = [], None, None, None
    if te is not None:
        test_pdf, test_pred_s = predict_to_pandas(best["model"], te, best["name"])
        test_cm = confusion_matrix(test_pdf[LABEL_COL].values, test_pdf[PRED_COL].values, len(labels))
        test_metrics, test_per_class = metrics_from_cm(test_cm, labels)
        log(f"== TEST (dùng một lần): {MODEL_NAMES[best['name']]} | acc {test_metrics['accuracy']:.4f} "
            f"| macro-F1 {test_metrics['macro_f1']:.4f} | weighted-F1 {test_metrics['weighted_f1']:.4f} "
            f"| {test_pred_s:.1f}s cho {len(test_pdf):,} dòng ==")
        test_rows.append(dict(model=MODEL_NAMES[best["name"]], split="test",
                              **{k: test_metrics[k] for k in ("accuracy", "weighted_f1", "macro_f1",
                                                              "macro_precision", "macro_recall", "n")},
                              best_params=fmt_params(best["params"]), n_candidates=best["n_candidates"],
                              n_features=best["n_features"], train_seconds=round(best["train_seconds"], 1),
                              predict_seconds_per_10k=round(test_pred_s / max(len(test_pdf), 1) * 10000, 2)))
        # baseline trên test trong CÙNG một lần chạm tập test (không huấn luyện gì thêm)
        major = int(tr.groupBy(LABEL_COL).count().orderBy(F.desc("count")).first()[0])
        base_pdf = (te.withColumn(PRED_COL, F.lit(float(major))).select(LABEL_COL, PRED_COL).toPandas())
        base_cm = confusion_matrix(base_pdf[LABEL_COL].values.astype(int),
                                   base_pdf[PRED_COL].values.astype(int), len(labels))
        base_m, _ = metrics_from_cm(base_cm, labels)
        test_rows.append(dict(model=MODEL_NAMES["baseline"], split="test",
                              **{k: base_m[k] for k in ("accuracy", "weighted_f1", "macro_f1",
                                                        "macro_precision", "macro_recall", "n")},
                              best_params="majority=" + labels[major], n_candidates=0, n_features=0,
                              train_seconds=0.0, predict_seconds_per_10k=0.0))
        for lab in labels:
            per_class_rows.append(dict(model=MODEL_NAMES[best["name"]], split="test", label=lab,
                                       **test_per_class[lab]))
        # Nhật ký mọi lần chạm tập test (quy tắc "test dùng một lần" — CLAUDE.md §6)
        import pandas as pd
        log_path = tables_dir / "test_eval_log.csv"
        entry = pd.DataFrame([{
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "model": MODEL_NAMES[best["name"]], "params": fmt_params(best["params"]),
            "n_test": test_metrics["n"], "accuracy": test_metrics["accuracy"],
            "macro_f1": test_metrics["macro_f1"], "weighted_f1": test_metrics["weighted_f1"],
            "sample_mode": bool(args.sample), "note": "đánh giá cuối cùng (Task 7)",
        }])
        entry.to_csv(log_path, mode="a", header=not log_path.exists(), index=False)

        # --- 6. Kiểm tra rò rỉ: chỉ số cao bất thường ----------------------
        thr = float(tcfg["leakage_threshold_macro_f1"])
        if test_metrics["macro_f1"] > thr:
            msg = (f"CẢNH BÁO RÒ RỈ: macro-F1 trên test = {test_metrics['macro_f1']:.4f} > ngưỡng {thr}. "
                   f"Trùng văn bản train↔test = {audit['trung_van_ban_train_test']}. "
                   f"KHÔNG lưu mô hình — cần kiểm tra lại dữ liệu trước khi báo cáo.")
            log(msg)
            (tables_dir / "leakage_alert.txt").write_text(msg + "\n", encoding="utf-8")
            if not args.sample:
                return 2

    # --- 7. Lưu bảng kết quả ------------------------------------------------
    import pandas as pd
    all_rows = val_rows + test_rows
    pd.DataFrame(all_rows).to_csv(tables_dir / "model_results.csv", index=False)
    pd.DataFrame(per_class_rows).to_csv(tables_dir / "per_class_metrics.csv", index=False)

    eval_split = "test" if test_cm is not None else "val"
    eval_cm = test_cm if test_cm is not None else best["cm"]
    eval_pc = test_per_class if test_per_class is not None else best["per_class"]
    eval_pdf = test_pdf if test_pdf is not None else best["pdf"]
    pd.DataFrame([dict(model=MODEL_NAMES[best["name"]], split=eval_split,
                       true_label=labels[i], pred_label=labels[j],
                       count=int(eval_cm[i, j]),
                       row_share=float(eval_cm[i, j] / max(eval_cm[i].sum(), 1)))
                  for i in range(len(labels)) for j in range(len(labels))]) \
        .to_csv(tables_dir / "confusion_matrix.csv", index=False)

    # Bảng/biểu đồ từ trọng số (mô hình tuyến tính)
    linear_src = best if best["name"] in ("lr", "svc") else next(
        (r for r in results if r["name"] == "lr"), None)
    df_top = None
    if linear_src is not None:
        df_top = top_features_table(linear_src, linear_src["name"], labels, int(tcfg["top_features_n"]))
        if df_top is not None:
            df_top.to_csv(tables_dir / "top_features.csv", index=False)

    df_err = error_analysis(eval_pdf, labels, tcfg["error_rules"], int(tcfg["error_n"]))
    if df_err is not None:
        df_err.to_csv(tables_dir / "error_analysis.csv", index=False)

    # --- 8. Biểu đồ ---------------------------------------------------------
    apply_style()          # bảng màu + backend Agg dùng chung cho mọi hình (CLAUDE.md §8)
    note = f"Source: data/processed/{eval_split}.parquet — {MODEL_NAMES[best['name']]} (Task 7)"
    plot_confusion(eval_cm, labels, figures_dir / "01_confusion_matrix.png", note,
                   f"Confusion matrix (row-normalized) — {MODEL_NAMES[best['name']]}, {eval_split}")
    plot_per_class(eval_pc, labels, figures_dir / "02_per_class_prf1.png", note,
                   f"Precision / Recall / F1 by class — {MODEL_NAMES[best['name']]}, {eval_split}")
    plot_model_comparison(all_rows, figures_dir / "03_model_comparison.png",
                          "Source: outputs/tables/model_results.csv (validation set)")
    if df_top is not None:
        plot_top_features(df_top, labels, figures_dir / "04_top_features.png",
                          f"Source: outputs/tables/top_features.csv — {MODEL_NAMES[linear_src['name']]}",
                          MODEL_NAMES[linear_src["name"]])
    if df_err is not None:
        plot_error_reasons(df_err, figures_dir / "05_error_reasons.png",
                           "Source: outputs/tables/error_analysis.csv")

    # --- 9. Lưu PipelineModel + metadata ------------------------------------
    model_out = PROJECT_ROOT / tcfg["model_out"]
    if not args.no_test:
        best["best_model"].write().overwrite().save(local_uri(model_out))
        meta = {
            "model_name": MODEL_NAMES[best["name"]],
            "model_slug": best["name"],
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "spark_version": spark.version,
            "seed": seed,
            "label_index": label_index,
            "label_source": "nhãn suy từ rating IMDb (1-4 negative / 5-6 neutral / 7-10 positive)",
            "best_params": {k: (float(v) if isinstance(v, (int, float)) else str(v))
                            for k, v in best["params"].items()},
            "vectorizer": {"vocab_size": len(best["best_model"].stages[3].vocabulary),
                           "min_df": float(tcfg["vectorizer"]["min_df"]),
                           "ngram": int(best["params"].get("ngram", 1)),
                           "normalize_l2": bool(tcfg.get("normalize_l2", True)),
                           "stopwords": len(stopwords), "keep_negations": bool(tcfg.get("keep_negations", True))},
            "class_weights": tcfg["class_weights"],
            "sizes": {"train": int(tr.count()), "val": int(va.count()),
                      "test": int(te.count()) if te is not None else None},
            "metrics": {"val": {k: best["metrics"][k] for k in
                                ("accuracy", "macro_f1", "weighted_f1", "n")},
                        "test": ({k: test_metrics[k] for k in
                                  ("accuracy", "macro_f1", "weighted_f1", "n")}
                                 if test_cm is not None else None)},
            "input_columns": ["text"],
            "text_column": "text",
            "pipeline_stages": [type(s).__name__ for s in best["best_model"].stages],
            "notes": [
                "Dự đoán trả về chỉ số lớp 0/1/2 — dịch sang tên lớp bằng label_index.",
                "SVC không có cột probability; LR/NB/RF có.",
                "Văn bản phải được làm sạch bằng src/common/text_cleaning.py trước khi đưa vào model.",
            ],
        }
        (model_out.parent / "sentiment_pipeline_metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"Đã lưu PipelineModel: {model_out}")
        log(f"Đã lưu metadata: {model_out.parent / 'sentiment_pipeline_metadata.json'}")
    else:
        log("Bỏ qua lưu mô hình (--no-test = chế độ chạy thử)")

    spark.stop()
    log("HOÀN TẤT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

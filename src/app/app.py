"""app.py — Dashboard gần thời gian thực cho luồng bình luận (Task 10, Day 10).

Ba tab:
  1. Live Monitor — tự làm mới, đọc **Parquet tổng hợp theo cửa sổ** của job
     streaming (Task 8): tỷ lệ cảm xúc hiện tại, cảm xúc theo phút, số bình
     luận/phút, độ trễ trung bình, biểu ngữ cảnh báo (ngưỡng chỉnh được) và
     10 bình luận mới nhất **đã che** (không hiện mã người dùng, che từ nhạy cảm).
  2. Try It — nạp `PipelineModel` bằng SparkSession local (cache `st.cache_resource`),
     chấm điểm một bình luận nhập tay: nhãn, xác suất từng lớp, và (với mô hình
     tuyến tính) những từ đóng góp nhiều nhất cho quyết định.
  3. About — pipeline, dữ liệu (nói rõ phần nào là REPLAY), hạn chế mô hình, riêng tư.

Nguyên tắc:
  - **Không hard-code đường dẫn tuyệt đối**: mọi đường dẫn suy ra từ vị trí file
    này + `config.yaml` (`src.common.utils.PROJECT_ROOT`).
  - **Không chạy Spark cho tab 1**: chỉ đọc Parquet đã ghi ra (dashboard không
    được làm chậm hay tranh tài nguyên với job streaming đang chạy).
  - **Chưa có dữ liệu là trạng thái bình thường**, không phải lỗi: mọi hàm đọc
    trả về DataFrame rỗng + thông báo, giao diện hiện hướng dẫn thay vì traceback.
  - **Mọi con số hiển thị đều lấy từ file thật** (CLAUDE.md §9) — không có số
    viết tay trong file này; các hằng số đều đọc từ `config.yaml`.

Chạy:
    source scripts/env.sh
    $VENV_PY -m streamlit run src/app/app.py --server.address 0.0.0.0 --server.port 8501
    # hoặc toàn bộ hệ thống (Kafka + job + producer + dashboard):
    bash scripts/run_demo.sh
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Cho phép `streamlit run src/app/app.py` từ bất kỳ thư mục nào: thêm gốc dự án
# (2 cấp trên file này) vào sys.path — KHÔNG hard-code '/home/hadoop/capstone'.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.plotting import SENTIMENT_COLORS          # noqa: E402
from src.common.utils import PROJECT_ROOT as _PR, load_config  # noqa: E402

assert _PR == PROJECT_ROOT, "PROJECT_ROOT tính từ file này phải khớp src.common.utils"

LABELS = ["negative", "neutral", "positive"]
LABEL_VI = {"negative": "Tiêu cực", "neutral": "Trung lập", "positive": "Tích cực"}
LABEL_EN = {"negative": "Negative", "neutral": "Neutral", "positive": "Positive"}
COLORS = [SENTIMENT_COLORS[l] for l in LABELS]

# Bảng dữ liệu (thư mục con trong outputs/stream/<run>/) và cột số để cộng dồn
WIN_TABLES = {"window_1min": "1 phút (nhảy)", "window_sliding_10s": "10 giây (trượt)"}
COUNT_COLS = ["n_comments", "n_negative", "n_neutral", "n_positive"]


# ---------------------------------------------------------------------------
# 1) Đọc dữ liệu — luôn trả về (DataFrame, thông báo lỗi) để giao diện tự quyết định
# ---------------------------------------------------------------------------
def read_table(sink: Path, name: str, tries: int = 3) -> tuple[pd.DataFrame, str | None]:
    """Đọc một bảng Parquet do job streaming ghi ra.

    Trả về `(df, lỗi)`. Ba tình huống được phân biệt rõ:
      - thư mục chưa tồn tại  -> (rỗng, None)   — job chưa chạy, KHÔNG phải lỗi;
      - thư mục rỗng          -> (rỗng, None)   — chưa có micro-batch nào ghi;
      - đọc lỗi               -> (rỗng, "…")   — thường do job đang ghi dở file;
        thử lại vài lần trước khi báo (đọc đồng thời với job đang chạy là bình thường
        chứ không phải sự cố).
    """
    path = sink / name
    if not path.exists():
        return pd.DataFrame(), None
    last_err: str | None = None
    for attempt in range(tries):
        try:
            df = pd.read_parquet(path)          # pyarrow tự bỏ qua file tạm (_*, .*)
            return df, None
        except Exception as e:                  # noqa: BLE001 — hiện nguyên văn cho người dùng
            last_err = f"{type(e).__name__}: {e}"
            if attempt < tries - 1:
                time.sleep(0.5 * (attempt + 1))
    return pd.DataFrame(), last_err


def list_runs(sink_root: Path) -> list[str]:
    """Các lần chạy có dữ liệu đọc được (thư mục con của outputs/stream/)."""
    if not sink_root.exists():
        return []
    out = []
    for p in sorted(sink_root.iterdir()):
        if p.is_dir() and any((p / t).exists() for t in list(WIN_TABLES) + ["scored_detail"]):
            out.append(p.name)
    return out


# ---------------------------------------------------------------------------
# 2) Biến đổi dữ liệu (hàm thuần — có test ở tests/test_dashboard.py)
# ---------------------------------------------------------------------------
def _add_shares(d: pd.DataFrame) -> pd.DataFrame:
    """Thêm `share_<lớp>` = n_<lớp> / n_comments (NaN khi cửa sổ rỗng)."""
    for l in LABELS:
        d[f"share_{l}"] = np.where(d.n_comments > 0, d[f"n_{l}"] / d.n_comments, np.nan)
    return d


def aggregate_windows(w: pd.DataFrame) -> pd.DataFrame:
    """Gộp cửa sổ của MỌI phòng (`stream_id`) thành một dòng cho mỗi cửa sổ.

    Job streaming ghi cửa sổ theo `(window, stream_id)` (xem src/streaming/README.md);
    dashboard cần nhìn toàn hệ thống nên phải cộng lại. Các cột trung bình
    (`avg_latency_ms`, `avg_confidence`) gộp theo **trọng số số bình luận** — lấy
    trung bình của các trung bình là sai khi các phòng lệch kích thước.
    """
    if w is None or w.empty:
        return pd.DataFrame()
    df = w.copy()
    for c in COUNT_COLS:
        if c not in df.columns:
            df[c] = 0
    d = df.groupby(["window_start", "window_end"], as_index=False)[COUNT_COLS].sum()
    for col in ("avg_latency_ms", "avg_confidence"):
        if col in df.columns:
            num = (df.assign(_x=df[col].fillna(0) * df.n_comments)
                     .groupby(["window_start", "window_end"], as_index=False)["_x"].sum())
            d = d.merge(num, on=["window_start", "window_end"], how="left")
            d[col] = np.where(d.n_comments > 0, d._x / d.n_comments, np.nan)
            d = d.drop(columns=["_x"])
    return _add_shares(d).sort_values("window_start").reset_index(drop=True)


def windows_from_detail(detail: pd.DataFrame, seconds: int) -> pd.DataFrame:
    """Dựng lại cửa sổ từ bảng CHI TIẾT (dùng khi cửa sổ của job chưa ra).

    Cửa sổ của job chỉ được ghi sau khi watermark (2 phút) vượt mốc kết thúc cửa sổ
    (src/streaming/README.md §5), nên vài phút đầu của một lần chạy mới thì
    `window_1min` còn rỗng trong khi `scored_detail` đã có dữ liệu. Hàm này tính
    **cùng định nghĩa cửa sổ** (theo `event_time`, không phải giờ hệ thống) để
    dashboard vẫn hiển thị được, và giao diện ghi rõ nguồn là bảng chi tiết.
    """
    if detail is None or detail.empty or "event_time" not in detail.columns:
        return pd.DataFrame()
    df = detail.copy()
    df["window_start"] = pd.to_datetime(df.event_time).dt.floor(pd.Timedelta(seconds=seconds))
    df["window_end"] = df.window_start + pd.Timedelta(seconds=seconds)
    cnt = (df.pivot_table(index=["window_start", "window_end"], columns="pred_label",
                          values="comment_id", aggfunc="count", fill_value=0)
             .reindex(columns=LABELS, fill_value=0)
             .rename(columns={l: f"n_{l}" for l in LABELS})
             .reset_index())
    cnt["n_comments"] = cnt[[f"n_{l}" for l in LABELS]].sum(axis=1)
    if "latency_ms" in df.columns:
        lat = (df.groupby("window_start", as_index=False)["latency_ms"].mean()
                 .rename(columns={"latency_ms": "avg_latency_ms"}))
        cnt = cnt.merge(lat, on="window_start", how="left")
    return _add_shares(cnt).sort_values("window_start").reset_index(drop=True)


def minute_from_detail(detail: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp theo PHÚT từ bảng chi tiết — dùng cho biểu đồ khi cửa sổ chậm."""
    return windows_from_detail(detail, 60)


def eval_alerts(agg: pd.DataFrame, threshold: float, min_comments: int,
                recent_s: int) -> dict:
    """Xét quy tắc cảnh báo trên các cửa sổ nằm trong `recent_s` giây CUỐI của dữ liệu.

    Cùng quy tắc đã đo ở Task 9 (`config.yaml → eda.alert`, xem outputs/insights.md
    hình 12): cảnh báo khi `share_negative > threshold` VÀ `n_comments >= min_comments`.
    Điều kiện số bình luận tối thiểu là bắt buộc: cửa sổ 1 bình luận luôn cho tỷ lệ
    0% hoặc 100% — đo ở Task 9 thấy bỏ điều kiện này sinh thêm 13 báo động giả.

    Mốc thời gian là **thời gian dữ liệu** (`window_end` lớn nhất), không phải giờ
    hệ thống: dữ liệu replay không xảy ra "bây giờ".
    """
    out = {"has_data": False, "alert": False, "recent": pd.DataFrame(),
           "n_recent": 0, "data_end": None, "share_negative": None, "n_comments": 0}
    if agg is None or agg.empty:
        return out
    data_end = pd.to_datetime(agg.window_end.max())
    recent = agg[pd.to_datetime(agg.window_end) > data_end - timedelta(seconds=recent_s)]
    recent = recent.sort_values("window_end")
    hits = recent[(recent.share_negative > threshold) & (recent.n_comments >= min_comments)]
    total = int(recent.n_comments.sum())
    out.update({
        "has_data": True, "recent": recent, "data_end": data_end,
        "alert": not hits.empty, "n_recent": len(recent),
        "share_negative": (float(recent.n_negative.sum() / total) if total else None),
        "n_comments": total,
        "hit": hits.iloc[-1] if not hits.empty else None,
    })
    return out


def mask_text(text: str, words: list[str], patterns: list[str]) -> str:
    """Che từ nhạy cảm và các mẫu nhạy cảm trước khi hiển thị (CLAUDE.md §7).

    - `words`: so khớp theo **ranh giới từ**, không phân biệt hoa/thường -> `***`.
      (`\\b` không đúng cho mọi ký tự Unicode, nhưng đủ cho dữ liệu tiếng Anh.)
    - `patterns`: regex thay cả cụm (email, số điện thoại) -> `[đã che]`.
    Không che từ nào thì trả về nguyên văn — hàm thuần, có test.
    """
    if not isinstance(text, str) or not text:
        return ""
    out = text
    for w in words or []:
        if not w:
            continue
        out = re.sub(rf"(?<!\w){re.escape(w)}(?!\w)", "***", out, flags=re.IGNORECASE)
    for p in patterns or []:
        if not p:
            continue
        out = re.sub(p, "[đã che]", out)
    return out


def fmt_utc(ts) -> str:
    """Mốc thời gian dữ liệu -> chuỗi UTC (mọi mốc trong dự án là UTC)."""
    if ts is None or pd.isna(ts):
        return "—"
    return pd.to_datetime(ts).strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# 3) Biểu đồ (plotly — dùng CHUNG bảng màu với hình trong báo cáo)
# ---------------------------------------------------------------------------
def chart_current(agg: pd.DataFrame) -> go.Figure:
    """Cơ cấu cảm xúc của cửa sổ mới nhất (thanh ngang, đơn vị %)."""
    last = agg.iloc[-1]
    fig = go.Figure(go.Bar(
        x=[last[f"share_{l}"] * 100 for l in LABELS],
        y=[LABEL_EN[l] for l in LABELS],
        orientation="h", marker_color=COLORS,
        text=[f"{last[f'share_{l}']*100:.0f}%  ({int(last[f'n_{l}'])})" for l in LABELS],
        textposition="outside", cliponaxis=False))
    fig.update_layout(
        title=f"Current sentiment mix — window {fmt_utc(last.window_start)}–{fmt_utc(last.window_end)} UTC",
        xaxis=dict(title="Share of comments (%)", range=[0, 108]),
        yaxis=dict(title=""), height=260, margin=dict(l=10, r=10, t=45, b=10),
        showlegend=False)
    return fig


def chart_timeline(minute: pd.DataFrame, source_note: str) -> go.Figure:
    """Diện tích xếp chồng số bình luận theo lớp, mỗi phút (đơn vị: bình luận)."""
    fig = go.Figure()
    for l in LABELS:
        fig.add_trace(go.Scatter(
            x=minute.window_start, y=minute[f"n_{l}"], name=LABEL_EN[l],
            mode="lines", stackgroup="one", line=dict(width=0.5, color=SENTIMENT_COLORS[l]),
            fillcolor=SENTIMENT_COLORS[l]))
    fig.update_layout(
        title=f"Comments per minute by predicted sentiment — {source_note}",
        xaxis=dict(title="Data time (UTC)"), yaxis=dict(title="Comments (count)"),
        height=320, margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(orientation="h", y=-0.25))
    return fig


def chart_volume(minute: pd.DataFrame) -> go.Figure:
    """Số bình luận mỗi phút (cột) — đơn vị: bình luận/phút."""
    fig = go.Figure(go.Bar(x=minute.window_start, y=minute.n_comments,
                           marker_color="#264653"))
    fig.update_layout(
        title="Comment volume", xaxis=dict(title="Data time (UTC)"),
        yaxis=dict(title="Comments per minute"), height=260,
        margin=dict(l=10, r=10, t=45, b=10), showlegend=False)
    return fig


def chart_probability(probs: dict[str, float]) -> go.Figure:
    """Xác suất mô hình gán cho từng lớp (đơn vị %)."""
    fig = go.Figure(go.Bar(
        x=[LABEL_EN[l] for l in LABELS], y=[probs[l] * 100 for l in LABELS],
        marker_color=COLORS,
        text=[f"{probs[l]*100:.1f}%" for l in LABELS], textposition="outside",
        cliponaxis=False))
    fig.update_layout(title="Model probability per class", yaxis=dict(title="Probability (%)",
                                                                      range=[0, 110]),
                      xaxis=dict(title="Class"), height=280, showlegend=False,
                      margin=dict(l=10, r=10, t=45, b=10))
    return fig


def chart_contributions(pairs: list[tuple[str, float]]) -> go.Figure:
    """Từ đóng góp nhiều nhất cho lớp được dự đoán (đơn vị: đóng góp có dấu)."""
    pairs = pairs[::-1]                      # vẽ từ dưới lên
    words = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]
    fig = go.Figure(go.Bar(x=vals, y=words, orientation="h",
                           marker_color=["#2A9D8F" if v > 0 else "#E76F51" for v in vals]))
    fig.update_layout(
        title="Top word contributions to the predicted class (linear model)",
        xaxis=dict(title="Contribution (weight × TF-IDF value, higher = stronger)"),
        yaxis=dict(title="Word (as tokenised)"), height=max(260, 26 * len(pairs)),
        margin=dict(l=10, r=10, t=45, b=10), showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# 4) Spark + PipelineModel cho tab "Try It" (nạp muộn, cache theo tiến trình)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_spark_model(model_path: str):
    """SparkSession local + PipelineModel — nạp MỘT lần cho cả phiên dashboard.

    `st.cache_resource`: Streamlit chạy lại script mỗi lần người dùng bấm nút, nếu
    không cache thì mỗi câu nhập tay sẽ dựng một SparkSession mới (chậm hàng chục
    giây và chiếm RAM). Chỉ gọi từ tab Try It — tab Live Monitor KHÔNG cần Spark.
    """
    from pyspark.ml import PipelineModel
    from pyspark.sql import SparkSession

    spark = (SparkSession.builder
             .appName("capstone-dashboard-try-it")
             .master("local[2]")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.ui.enabled", "false")     # không mở UI Spark cho dashboard
             .config("spark.sql.shuffle.partitions", "4")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    model = PipelineModel.load("file://" + model_path)   # thiếu file:// là Spark tìm trên HDFS
    return spark, model


def linear_parts(model):
    """(vocabulary, ma trận hệ số) của mô hình tuyến tính trong Pipeline.

    Trả về `(None, None)` nếu Pipeline không phải mô hình tuyến tính có từ vựng
    (ví dụ RandomForest) — khi đó tab Try It chỉ hiện nhãn + xác suất.
    """
    vocab = coef = None
    for stage in model.stages:
        name = type(stage).__name__
        if name == "CountVectorizerModel":
            vocab = stage.vocabulary
        elif name == "LogisticRegressionModel":
            coef = np.asarray(stage.coefficientMatrix.toArray())
    return vocab, coef


def score_comment(text: str, cfg: dict) -> dict:
    """Làm sạch + chấm điểm một bình luận. Trả về dict để giao diện hiển thị.

    Làm sạch bằng **đúng hàm dùng lúc huấn luyện** (`clean_text`) — nhờ vậy câu nhập
    tay đi qua đúng đường đi của dữ liệu thật (CLAUDE.md §4).
    """
    from pyspark.sql import functions as F

    from src.common.text_cleaning import clean_text

    model_path = str(PROJECT_ROOT / cfg["training"]["model_out"])
    spark, model = get_spark_model(model_path)
    abbrev = cfg["cleaning"]["abbreviations"]

    df = spark.createDataFrame([(text,)], "text string")
    df = df.withColumn("text", clean_text(F.col("text"), abbrev))
    cleaned = df.first()["text"]
    row = model.transform(df).select("prediction", "probability", "features").first()

    probs = {l: float(p) for l, p in zip(LABELS, list(row["probability"]))}
    pred_idx = int(row["prediction"])
    pred_label = LABELS[pred_idx] if 0 <= pred_idx < len(LABELS) else f"lớp #{pred_idx}"
    result = {"cleaned": cleaned, "pred_label": pred_label, "probs": probs,
              "contributions": [], "vocab_note": None}

    vocab, coef = linear_parts(model)
    feat = row["features"]
    if vocab is not None and coef is not None and pred_idx < coef.shape[0]:
        pairs = [(vocab[i], float(feat.values[k] * coef[pred_idx, i]))
                 for k, i in enumerate(feat.indices)]
        pairs.sort(key=lambda t: -t[1])
        top = pairs[:8] + pairs[-4:]                 # 8 từ đóng góp dương + 4 âm
        seen, uniq = set(), []
        for w, v in top:
            if w not in seen:
                seen.add(w)
                uniq.append((w, v))
        result["contributions"] = uniq
    elif vocab is None:
        result["vocab_note"] = ("Mô hình đang dùng không phải mô hình tuyến tính nên "
                                "không có 'từ đóng góp'.")
    return result


# ---------------------------------------------------------------------------
# 5) Tab 1 — Live Monitor
# ---------------------------------------------------------------------------
def tab_live(cfg: dict, dash: dict, sink: Path, refresh_s: int,
             threshold: float, min_comments: int, show_ids: bool):
    detail, err_d = read_table(sink, "scored_detail")
    win1, err_w1 = read_table(sink, "window_1min")
    slide, err_s = read_table(sink, "window_sliding_10s")

    for err, what in ((err_d, "scored_detail"), (err_w1, "window_1min"),
                      (err_s, "window_sliding_10s")):
        if err:
            st.warning(f"Đọc `{what}` lỗi (job đang ghi dở?) — đã thử lại 3 lần: {err}")

    if detail.empty and win1.empty and slide.empty:
        st.info(
            "**Chưa có dữ liệu cho lần chạy này.** Job streaming chưa ghi bản ghi nào "
            f"vào `{sink.relative_to(PROJECT_ROOT)}`.\n\n"
            "Chạy toàn bộ hệ thống (Kafka → job → producer → dashboard) bằng một lệnh:\n\n"
            "```bash\nbash scripts/run_demo.sh\n```\n\n"
            "hoặc phát lại dữ liệu cũ đã có sẵn: `outputs/stream/verify1` (Task 8).")
        return

    agg_slide = aggregate_windows(slide)
    agg_win = aggregate_windows(win1)

    # --- chọn nguồn cho biểu đồ theo phút -----------------------------------
    detail_last = pd.to_datetime(detail.event_time).max() if not detail.empty else None
    win_last = pd.to_datetime(agg_win.window_end).max() if not agg_win.empty else None
    lag = (detail_last - win_last).total_seconds() if (detail_last is not None
                                                       and win_last is not None) else None
    if not agg_win.empty and (lag is None or lag <= 90):
        minute, source = agg_win, "cửa sổ 1 phút của job streaming"
    else:
        minute, source = minute_from_detail(detail), "bảng chi tiết (cửa sổ chưa kịp ra)"
        if not agg_win.empty and lag is not None:
            st.info(f"Cửa sổ 1 phút đang chậm hơn bảng chi tiết **{lag:.0f} giây** — đúng "
                    "ngữ nghĩa watermark 2 phút (cửa sổ chỉ ghi khi watermark vượt mốc "
                    "kết thúc cửa sổ). Biểu đồ dưới đây tạm tính từ bảng chi tiết.")

    # --- trạng thái hiện tại + cảnh báo -------------------------------------
    agg_now = agg_slide if not agg_slide.empty else agg_win
    if agg_now.empty:
        # Chưa cửa sổ nào được ghi (watermark 2 phút) -> dựng cửa sổ 10 giây từ
        # bảng chi tiết. Cùng định nghĩa cửa sổ, khác nguồn; giao diện ghi rõ.
        agg_now = windows_from_detail(detail, int(dash["current_window_s"]))
    state = eval_alerts(agg_now, threshold, min_comments, int(dash["current_window_s"]))

    # Khối mô tả dữ liệu đang xem (mốc thời gian là thời gian DỮ LIỆU)
    total = int(len(detail)) if not detail.empty else int(agg_now.n_comments.sum()) \
        if not agg_now.empty else 0
    st.caption(
        f"Lần chạy `{sink.name}` · dữ liệu đến **{fmt_utc(detail_last if detail_last is not None else state['data_end'])} UTC** "
        f"· tổng **{total:,} bình luận** đã chấm điểm · đọc lúc "
        f"{datetime.now().strftime('%H:%M:%S')} (giờ máy) · nguồn biểu đồ: {source}")

    # --- biểu ngữ cảnh báo ---------------------------------------------------
    thr_txt = f"{threshold:.0%} và ≥ {min_comments} bình luận"
    if state["alert"]:
        hit = state["hit"]
        st.error(
            f"🚨 **CẢNH BÁO: tỷ lệ tiêu cực vượt ngưỡng** — "
            f"cửa sổ {fmt_utc(hit.window_start)}–{fmt_utc(hit.window_end)} UTC có "
            f"**{hit.share_negative:.1%} tiêu cực** ({int(hit.n_negative)}/{int(hit.n_comments)} "
            f"bình luận), vượt ngưỡng {thr_txt}. Đề xuất: mở khung bình luận mới nhất bên "
            "dưới và tăng người kiểm duyệt cho phòng đang bị ảnh hưởng.")
    elif state["has_data"]:
        st.success(f"✅ Không có cửa sổ nào vượt ngưỡng cảnh báo ({thr_txt}) trong "
                   f"{state['n_recent']} cửa sổ gần nhất. Tỷ lệ tiêu cực hiện tại: "
                   f"{state['share_negative']:.1%} trên {state['n_comments']} bình luận.")
    else:
        st.info("Chưa đủ dữ liệu để xét cảnh báo.")

    # --- chỉ số chính --------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bình luận (cửa sổ hiện tại)", f"{state['n_comments']:,}"
              if state["has_data"] else "—")
    if state["share_negative"] is not None:
        base = None
        try:      # tỷ lệ nền của tập test (số thật trong outputs/tables)
            cd = pd.read_csv(PROJECT_ROOT / "outputs" / "tables" / "class_distribution.csv")
            base = float(cd[cd.split == "test"].set_index("label")
                         .loc["negative", "share_in_split"])
        except Exception:                     # noqa: BLE001 — thiếu file thì bỏ mốc so sánh
            base = None
        c2.metric("Tỷ lệ tiêu cực",
                  f"{state['share_negative']:.1%}",
                  delta=(f"{(state['share_negative'] - base) * 100:+.1f} điểm % so với nền "
                         f"{base:.1%}") if base is not None else None,
                  delta_color="inverse")
    else:
        c2.metric("Tỷ lệ tiêu cực", "—")

    if not detail.empty and "latency_ms" in detail.columns:
        lat = detail.loc[pd.to_datetime(detail.event_time)
                         > (detail_last - timedelta(minutes=1)), "latency_ms"]
        c3.metric("Độ trễ trung bình (1 phút cuối)",
                  f"{lat.mean()/1000:.2f} s" if len(lat) else "—",
                  delta=f"p95 {lat.quantile(0.95)/1000:.2f} s" if len(lat) else None,
                  delta_color="off")
    else:
        c3.metric("Độ trễ trung bình", "—")

    if not minute.empty:
        last_min = minute.iloc[-1]
        c4.metric("Bình luận/phút (phút gần nhất)", f"{int(last_min.n_comments):,}",
                  delta=f"trung bình {minute.n_comments.mean():.0f}/phút",
                  delta_color="off")
    else:
        c4.metric("Bình luận/phút", "—")

    # --- biểu đồ -------------------------------------------------------------
    left, right = st.columns([1, 2])
    if not agg_now.empty:
        left.plotly_chart(chart_current(agg_now), width="stretch")
    if not minute.empty:
        right.plotly_chart(chart_timeline(minute.tail(int(dash["recent_minutes"])), source),
                           width="stretch")
    if not minute.empty:
        st.plotly_chart(chart_volume(minute.tail(int(dash["recent_minutes"]))),
                        width="stretch")

    # --- bình luận mới nhất (đã che) ----------------------------------------
    st.subheader(f"{int(dash['latest_comments_n'])} bình luận mới nhất (đã ẩn danh)")
    if detail.empty:
        st.info("Chưa có bình luận nào trong bảng chi tiết.")
        return

    has_text = "text_clean" in detail.columns
    cols = ["event_time", "stream_id", "pred_label", "confidence", "latency_ms", "text_len"]
    latest = (detail.sort_values("event_time", ascending=False)
                    .head(int(dash["latest_comments_n"])))
    out = pd.DataFrame({
        "Thời điểm (UTC)": pd.to_datetime(latest.event_time).dt.strftime("%H:%M:%S"),
        "Phòng (stream_id)": latest.stream_id.values,
        "Dự đoán": [LABEL_VI.get(v, v) for v in latest.pred_label],
        "Độ tin cậy": [f"{v:.0%}" for v in latest.confidence],
        "Độ trễ (s)": [f"{v/1000:.1f}" for v in latest.latency_ms],
        "Số ký tự": latest.text_len.values,
    })
    if has_text:
        out["Bình luận (đã che)"] = [mask_text(t, dash["mask_words"], dash["mask_patterns"])
                                     for t in latest.text_clean.values]
    if show_ids:
        out["Mã bình luận"] = latest.comment_id.values

    if not has_text:
        st.warning(
            "Lần chạy này **không lưu văn bản** (`streaming.privacy.keep_text: false`) — "
            "đúng quy ước riêng tư, nên chỉ hiện được thông tin tổng hợp. Muốn thấy nội "
            "dung đã che thì chạy lại job với `--keep-text` (`scripts/run_demo.sh` đã bật "
            "sẵn cho dữ liệu demo công khai).")
    st.dataframe(out, width="stretch", hide_index=True)

    missing = [c for c in ("user_hash", "comment_id") if c in detail.columns]
    st.caption("Bảng này **không hiển thị mã người dùng** (`user_hash` đã bị bỏ khỏi "
               "khung nhìn)" + ("; mã bình luận chỉ hiện khi bật ô 'Hiện mã bình luận'."
                                if "comment_id" in missing else ".") +
               " Từ nhạy cảm bị thay bằng `***`, email/số điện thoại bằng `[đã che]` "
               "(danh sách ở `config.yaml → dashboard.mask_words`).")
    st.caption("⚠️ Dữ liệu demo là **REPLAY** (phát lại review IMDb), không phải bình luận "
               "livestream thật — xem tab **About**.")


# ---------------------------------------------------------------------------
# 6) Tab 2 — Try It
# ---------------------------------------------------------------------------
def tab_try_it(cfg: dict, dash: dict):
    st.markdown("Nhập một bình luận để xem mô hình dự đoán gì. Câu nhập được **làm sạch "
                "bằng đúng hàm dùng lúc huấn luyện** (`src/common/text_cleaning.py`) rồi "
                "mới đưa vào `PipelineModel` — cùng đường đi với dữ liệu thật.")

    if "try_it_text" not in st.session_state:
        st.session_state.try_it_text = ""

    st.caption("Câu ví dụ (bấm để điền vào ô nhập):")
    ex_cols = st.columns(len(dash["try_it_examples"]))
    for col, ex in zip(ex_cols, dash["try_it_examples"]):
        if col.button(ex[:38] + ("…" if len(ex) > 38 else ""), width="stretch",
                      help=ex):
            st.session_state.try_it_text = ex

    text = st.text_area("Bình luận (tiếng Anh — mô hình huấn luyện trên dữ liệu tiếng Anh)",
                        key="try_it_text", height=110,
                        placeholder="ví dụ: the acting is good. the story is very much lacking")

    c1, c2 = st.columns([1, 3])
    run = c1.button("Phân tích", type="primary", width="stretch")
    c2.caption("Lần đầu bấm sẽ mất ~15–30 giây để dựng SparkSession và nạp mô hình "
               "(các lần sau dùng lại, nhờ `st.cache_resource`).")

    if not run:
        return
    if not text or not text.strip():
        st.warning("Chưa nhập gì — hãy nhập một bình luận.")
        return

    n_chars = len(text.strip())
    if n_chars < int(cfg["cleaning"]["min_chars"]):
        st.warning(f"Bình luận chỉ có {n_chars} ký tự, ngắn hơn `cleaning.min_chars` = "
                   f"{cfg['cleaning']['min_chars']} → trong luồng thật bản ghi này sẽ vào "
                   "**DLQ** (`van_ban_qua_ngan...`). Kết quả dưới đây chỉ để tham khảo.")

    try:
        with st.spinner("Đang chấm điểm bằng Spark ML ..."):
            res = score_comment(text, cfg)
    except Exception as e:                    # noqa: BLE001 — hiện nguyên văn cho người dùng
        st.error(f"Không chấm điểm được: `{type(e).__name__}: {e}`\n\n"
                 "Kiểm tra: đã `source scripts/env.sh` chưa (JAVA_HOME/PYSPARK_PYTHON), "
                 f"và mô hình có tồn tại ở `{cfg['training']['model_out']}` không.")
        return

    st.success(f"**Dự đoán: {LABEL_VI.get(res['pred_label'], res['pred_label'])}** "
               f"(`{res['pred_label']}`, độ tin cậy {res['probs'][res['pred_label']]:.1%})")

    left, right = st.columns([1, 1])
    with left:
        st.plotly_chart(chart_probability(res["probs"]), width="stretch")
    with right:
        if res["contributions"]:
            st.plotly_chart(chart_contributions(res["contributions"]),
                            width="stretch")
        elif res["vocab_note"]:
            st.info(res["vocab_note"])

    with st.expander("Văn bản sau khi làm sạch (đây là thứ mô hình thực sự đọc)"):
        st.code(res["cleaned"] or "(rỗng)", language=None)
    st.caption("Từ đóng góp = trọng số mô hình × giá trị TF-IDF. Thanh **xanh** đẩy về "
               "lớp được dự đoán, thanh **cam đỏ** kéo ra khỏi lớp đó. Dấu câu còn dính "
               "vào từ (`movie!`) vì bước tách từ chỉ dựa vào khoảng trắng — hạn chế đã "
               "biết, xem tab About.")


# ---------------------------------------------------------------------------
# 7) Tab 3 — About
# ---------------------------------------------------------------------------
def tab_about(cfg: dict, dash: dict):
    meta_path = PROJECT_ROOT / (cfg["training"]["model_out"] + "_metadata.json")
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:                # noqa: BLE001
            st.warning(f"Đọc metadata mô hình lỗi: {e}")

    st.markdown("### Pipeline")
    st.code(
        "IMDb review (JSON)  ──►  Kafka topic comments_raw\n"
        "        │                        │\n"
        "        │                        ├─► Spark Structured Streaming (6 query)\n"
        "        │                        │      làm sạch (clean_text) → PipelineModel → 3 đích:\n"
        "        │                        │        (a) Parquet chi tiết   (b) topic comments_scored\n"
        "        │                        │        (c) Parquet cửa sổ 1 phút / 10 giây trượt\n"
        "        │                        └─► DLQ (topic + Parquet) kèm LÝ DO cho bản ghi lỗi\n"
        "        ▼\n"
        "  (offline) prepare.py → train.py → PipelineModel (TF-IDF + LogisticRegression)\n"
        "        │\n"
        "        └─► DASHBOARD (file này): Live Monitor ← Parquet cửa sổ;  Try It ← PipelineModel",
        language=None)

    st.markdown("### Dữ liệu — phần nào là MÔ PHỎNG")
    st.markdown(
        "- Nguồn: **IMDb Review Dataset (ebD, CC0)**, lấy mẫu 20% (xem `data/raw/SOURCE.md`). "
        "Đây là **review phim**, không phải bình luận livestream.\n"
        "- Nhãn **suy từ điểm `rating`** 1–10 (1–4 tiêu cực, 5–6 trung lập, 7–10 tích cực) "
        "— quy ước của nhóm, **không** phải nhãn cảm xúc do người gán.\n"
        "- Luồng Kafka là **REPLAY**: `replay_producer.py` phát lại review có sẵn với `event_ts` "
        "do chương trình gán. **Không phải dữ liệu livestream thật**, và không có người xem thật.\n"
        "- ⇒ Mọi kết luận về *hành vi người xem* chỉ minh hoạ cho cơ chế, **cần đo lại** khi có "
        "dữ liệu thật.")

    size_cells = []
    for split in ("train", "val", "test"):
        if meta.get("sizes", {}).get(split):
            size_cells.append(f"**{split}** {meta['sizes'][split]:,}")
    st.markdown("### Mô hình đang chạy")
    st.markdown(
        f"- `{cfg['training']['model_out']}` — **{meta.get('model_name', '?')}**, "
        f"TF-IDF {meta.get('vectorizer', {}).get('vocab_size', '?')} đặc trưng, "
        f"{meta.get('vectorizer', {}).get('stopwords', '?')} stopword (giữ từ phủ định), "
        f"trọng số lớp `{meta.get('class_weights', '?')}`, huấn luyện {meta.get('saved_at', '?')}."
        + (" Dữ liệu: " + " · ".join(size_cells) + " bình luận." if size_cells else ""))
    try:
        pcm = pd.read_csv(PROJECT_ROOT / "outputs" / "tables" / "per_class_metrics.csv")
        test = pcm[pcm.split == "test"] if "split" in pcm.columns else pcm
        if "model" in test.columns and test.model.nunique() > 1 and meta.get("model_name"):
            test = test[test.model == meta["model_name"]]     # chỉ mô hình đang chạy
        rows = "\n".join(
            f"| {LABEL_VI.get(r.label, r.label)} | {r.precision:.2f} | {r.recall:.2f} | "
            f"**{r.f1:.2f}** | {int(r.support):,} |" for r in test.itertuples())
        st.markdown("| Lớp | Precision | Recall | F1 | Số mẫu (test) |\n|---|---|---|---|---|\n"
                    + rows + "\n\n*(số thật từ `outputs/tables/per_class_metrics.csv`)*")
    except Exception as e:                    # noqa: BLE001
        st.info(f"Chưa đọc được `per_class_metrics.csv` ({type(e).__name__}) — chạy Task 7 trước.")

    st.markdown("### Hạn chế (phải nói rõ khi báo cáo)")
    st.markdown(
        "1. **Mỉa mai** — TF-IDF 1-gram không có ngữ cảnh nên **về nguyên tắc** không phát "
        "hiện được mỉa mai. Đo thật trên 4 câu ví dụ ở tab Try It (15/10/2026): câu mỉa mai "
        "*\"his 'bad acting' had me crying with laughter, absolutely brilliant\"* lại được "
        "đoán **đúng** là tích cực (86 %) vì mô hình bắt được `laughter`/`brilliant` — nghĩa "
        "là **câu dễ thì đúng, câu khó thì không, và không biết trước là câu nào**. Trong 30 "
        "bình luận đoán sai ở Task 7, 5 ca phải đọc tay mới hiểu (`error_analysis.csv`).\n"
        "2. **Domain shift** — mô hình học trên **review phim dài**, trong khi bình luận "
        "livestream **ngắn, teencode, nhiều emoji**. Kết quả trên luồng thật **có thể thấp hơn**.\n"
        "3. **Ngôn ngữ** — huấn luyện hoàn toàn bằng **tiếng Anh**; bình luận tiếng Việt sẽ "
        "cho kết quả vô nghĩa. Muốn hỗ trợ tiếng Việt phải thêm tách từ tiếng Việt và "
        "**huấn luyện lại** (chi phí chưa đo).\n"
        "4. **Nhãn là suy diễn từ điểm số** — lớp *trung lập* là điểm yếu nhất (xem bảng "
        "trên): F1 chỉ ~0,38, tức phần lớn bình luận trung lập bị đoán sai. Khi dashboard báo "
        "*trung lập*, nên coi là **cần người xem lại**, không phải kết luận.\n"
        "5. **Mô hình dựa vào điểm số người viết tự ghi** — đo thật: câu `it was okay, nothing "
        "special. 6/10` (ví dụ số 2 ở tab Try It) cho **trung lập 99 %**, và từ đóng góp lớn "
        "nhất chính là token `6/10` (**+3,27**, lớn hơn mọi từ cảm xúc). Bình luận livestream "
        "hiếm khi ghi điểm ⇒ **đừng hứa** chỉ số của báo cáo là năng lực thật trên livestream.\n"
        "6. **Trộn hai ý trong một bình luận** — câu `the acting is good. the story is very "
        "much lacking` cho **trung lập 66 %** với `lacking` là từ đóng góp mạnh nhất: mô hình "
        "không dung hoà được hai vế trái chiều, chỉ cộng dồn từ khoá.\n"
        "7. Cửa sổ kết quả **ra chậm ~2 phút** so với thời điểm bình luận (watermark) — "
        "dashboard hiện dữ liệu theo *thời gian dữ liệu*, không phải theo giờ hệ thống.")

    st.markdown("### Quyền riêng tư")
    st.markdown(
        "- Mã người dùng được **băm có muối** (SHA-256, muối trong biến môi trường, không "
        "nằm trong repo) và **không hiển thị trên dashboard**.\n"
        "- Mặc định job streaming **không lưu văn bản** (`streaming.privacy.keep_text: false`) "
        "— chỉ giữ `text_len` + băm văn bản để phát hiện copy-paste.\n"
        "- Khung *bình luận mới nhất* là ngoại lệ **chỉ dùng cho demo trên dữ liệu công khai** "
        "(`run_demo.sh` bật `--keep-text`), và vẫn che từ nhạy cảm + email/số điện thoại. "
        "Khi thu bình luận thật: **tắt** tính năng này, chỉ hiển thị số liệu tổng hợp.\n"
        "- Không hiển thị tên/ID thật/email/số điện thoại (CLAUDE.md §7).")

    st.markdown("### Chạy lại")
    st.code("bash scripts/run_demo.sh              # Kafka → job → producer → dashboard\n"
            "bash scripts/run_demo.sh --stop       # dừng sạch toàn bộ\n"
            "bash scripts/run_demo.sh --help       # các tuỳ chọn (rate, thời lượng, ...)",
            language="bash")


# ---------------------------------------------------------------------------
# 8) main — sidebar + 3 tab
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="CommentStreaming — Cảm xúc bình luận",
                       page_icon="💬", layout="wide")

    cfg = load_config()
    dash = cfg["dashboard"]
    sink_root = PROJECT_ROOT / cfg["streaming"]["sink_root"]

    st.title("💬 CommentStreaming — dashboard gần thời gian thực")
    st.caption("Nhóm 6 · Samsung Innovation Campus — Big Data · mô hình phân loại cảm xúc "
               "bình luận trực tuyến")

    # --- sidebar -------------------------------------------------------------
    runs = list_runs(sink_root)
    default_run = str(dash["streaming_run"])
    if not runs:
        st.warning(f"Chưa có lần chạy streaming nào trong `{sink_root.relative_to(PROJECT_ROOT)}`. "
                   "Chạy `bash scripts/run_demo.sh` để tạo dữ liệu demo.")
        run = default_run
    else:
        idx = runs.index(default_run) if default_run in runs else len(runs) - 1
        run = st.sidebar.selectbox("Lần chạy streaming", runs, index=idx,
                                   help="Đọc từ outputs/stream/<tên>/ (mỗi query một "
                                        "checkpoint, xem src/streaming/README.md)")
    sink = sink_root / run
    st.sidebar.caption(f"Nguồn: `{sink.relative_to(PROJECT_ROOT)}`")

    auto = st.sidebar.toggle("Tự động làm mới (Live Monitor)", value=True)
    refresh_s = st.sidebar.slider("Nhịp làm mới (giây)", 2, 30,
                                  int(dash["refresh_seconds"]),
                                  disabled=not auto)
    st.sidebar.divider()
    st.sidebar.markdown("**Cảnh báo tỷ lệ tiêu cực**")
    threshold = st.sidebar.slider("Ngưỡng tỷ lệ tiêu cực (%)", 5, 90,
                                  int(float(cfg["eda"]["alert"]["negative_share_threshold"]) * 100),
                                  step=5,
                                  help="Mặc định lấy từ config.yaml → eda.alert"
                                       f" (nền: {cfg['eda']['alert']['basis']})") / 100.0
    min_comments = st.sidebar.number_input(
        "Số bình luận tối thiểu trong cửa sổ", min_value=1, max_value=100,
        value=int(cfg["eda"]["alert"]["min_comments"]),
        help="Bắt buộc: cửa sổ 1 bình luận luôn cho tỷ lệ 0% hoặc 100%.")
    show_ids = st.sidebar.checkbox("Hiện mã bình luận (truy vết)", value=False,
                                   help="Mặc định ẩn để đúng quy ước ẩn danh.")
    st.sidebar.divider()
    st.sidebar.caption(f"Spark: {cfg['training']['model_out']}\n\n"
                       "Dữ liệu luồng là **replay** — xem tab About.")

    # --- 3 tab ---------------------------------------------------------------
    t1, t2, t3 = st.tabs(["📊 Live Monitor", "🧪 Try It", "ℹ️ About"])

    with t2:
        tab_try_it(cfg, dash)
    with t3:
        tab_about(cfg, dash)
    with t1:
        if auto:
            # Fragment = chỉ vùng này được vẽ lại theo nhịp, không vẽ lại cả trang
            # (đổi lại: ô nhập ở tab Try It không bị xoá khi bảng tự làm mới).
            body = st.fragment(run_every=f"{int(refresh_s)}s")(tab_live)
        else:
            if st.button("Làm mới ngay"):
                st.rerun()
            body = tab_live
        body(cfg, dash, sink, int(refresh_s), threshold, int(min_comments), show_ids)


if __name__ == "__main__":
    main()

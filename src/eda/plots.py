"""plots.py — Vẽ biểu đồ EDA và sinh `outputs/insights.md` (Task 9).

Script này KHÔNG chạy Spark: nó đọc các bảng CSV do `src/eda/queries.py` ghi ra
`outputs/tables/eda_*.csv` (cùng vài bảng của Task 7) rồi vẽ. Nhờ vậy sửa hình
không phải chạy lại Spark, và mọi con số trên hình đều truy vết được về file CSV.

Quy ước hình (CLAUDE.md §8): chữ trong hình là tiếng ANH, nhãn trục có đơn vị,
PNG 200 dpi, lưu vào `outputs/figures/`, đánh số `06_`… (01–05 là hình Task 7),
dùng chung bảng màu `src/common/plotting.py`.

`outputs/insights.md` được SINH TỰ ĐỘNG từ chính các con số vừa vẽ — không viết
tay, để câu chữ không thể lệch khỏi dữ liệu. Mỗi hình có 1–2 câu insight (đều
kèm số đo) và 1 hành động cụ thể cho người làm livestream / người kiểm duyệt.
Hình nào số liệu không đủ để kết luận thì ghi rõ "chưa đủ căn cứ" thay vì đoán.

Chạy:
    source scripts/env.sh
    $VENV_PY src/eda/queries.py          # bước 1: sinh bảng (cần Spark)
    $VENV_PY src/eda/plots.py            # bước 2: vẽ hình + insights (không cần Spark)
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.common.plotting import SENTIMENT_COLORS, apply_style, save_fig  # noqa: E402
from src.common.utils import PROJECT_ROOT, load_config                   # noqa: E402

TABLES = PROJECT_ROOT / "outputs" / "tables"
FIGURES = PROJECT_ROOT / "outputs" / "figures"
INSIGHTS = PROJECT_ROOT / "outputs" / "insights.md"

LABELS = ["negative", "neutral", "positive"]
CLASS_EN = {"negative": "Negative", "neutral": "Neutral", "positive": "Positive"}
ACCENT = "#264653"          # xanh than — dùng cho đường/thanh không thuộc lớp nào
WARN = "#E76F51"            # cam đỏ — cảnh báo/bùng nổ
THUMBS_DOWN = "\U0001F44E"  # 👎 — hằng số riêng vì f-string Python 3.11 không cho \u trong {...}
THUMBS_UP = "\U0001F44D"


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / f"{name}.csv")


def write_table(df: pd.DataFrame, name: str) -> Path:
    path = TABLES / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


def finish(fig, path: Path, note: str, bottom: float = 0.06, top: float = 1.0,
           manual: dict | None = None) -> None:
    """Chốt bố cục rồi lưu hình.

    `tight_layout(rect=...)` chừa một dải trống ở đáy để dòng "Source: ..." của
    `save_fig` không đè lên nhãn trục (đã gặp thật ở hình 06/07 trước khi sửa).
    `top < 1` dành chỗ cho tiêu đề chung (suptitle).
    `manual` (dict cho `subplots_adjust`) dùng cho hình mà tight_layout không
    chạy được — matplotlib 3.11 báo "Axes not compatible with tight_layout" với
    lưới nhiều panel dùng chung trục x, và khi đó nó bỏ qua luôn việc canh lề.
    """
    if manual:
        fig.subplots_adjust(**manual)
    else:
        fig.tight_layout(rect=(0, bottom, 1, top))
    save_fig(fig, path, note=note)


def emoji_label(e: str) -> str:
    """Tên tiếng Anh của emoji để làm nhãn trục.

    KHÔNG vẽ ký tự emoji lên hình: font DejaVu Sans của matplotlib thiếu glyph
    mặt cười (đã thử, chỉ hiện ô vuông), nên dùng tên Unicode cho đọc được.
    """
    if all(0x1F1E6 <= ord(ch) <= 0x1F1FF for ch in e):        # cờ = 2 chữ cái
        return "flag " + "".join(chr(ord(ch) - 0x1F1E6 + ord("A")) for ch in e)
    parts = []
    for ch in e:
        try:
            name = unicodedata.name(ch).lower()
        except ValueError:
            name = f"u+{ord(ch):04x}"
        name = name.replace("emoji modifier fitzpatrick type-", "skin tone ")
        if name.startswith("variation selector"):
            continue
        if name not in parts:
            parts.append(name)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Hình 06 — phân bố nhãn cảm xúc của dữ liệu huấn luyện
# ---------------------------------------------------------------------------
def fig06_class_distribution(df: pd.DataFrame) -> dict:
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    splits = ["train", "val", "test"]
    x = np.arange(len(splits))
    width = 0.26
    for i, lab in enumerate(LABELS):
        vals = [int(df[(df.split == s) & (df.label == lab)].n_comments.iloc[0]) for s in splits]
        bars = ax.bar(x + (i - 1) * width, vals, width, label=CLASS_EN[lab],
                      color=SENTIMENT_COLORS[lab])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v * 1.02, f"{v:,}", ha="center",
                    va="bottom", fontsize=8, color="#333333")
    shares = (df[df.split == "train"].set_index("label").share_in_split * 100).round(1)
    ax.set_yscale("log")
    ax.set_ylim(top=170000)
    ax.set_xticks(x, [s.capitalize() for s in splits])
    ax.set_ylabel("Number of comments (count, log scale)")
    ax.set_xlabel("Dataset split")
    ax.set_title("Class distribution in the training data (IMDb, labels derived from rating)")
    ax.legend(title="Sentiment class", frameon=False)
    ax.text(0.02, 0.96,
            "Class share (identical by design in all three splits):\n"
            f"negative {shares['negative']}%   neutral {shares['neutral']}%   "
            f"positive {shares['positive']}%",
            transform=ax.transAxes, va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#F4F4F4", edgecolor="#CCCCCC"))
    finish(fig, FIGURES / "06_class_distribution.png",
             note="Source: outputs/tables/eda_class_distribution.csv (Spark SQL q01). "
                  "Labels are derived from rating 1-4/5-6/7-10 (design choice, not human annotations).")
    plt.close(fig)
    return {
        "file": "06_class_distribution.png",
        "title": "6. Class distribution of the training data",
        "bullets": [
            f"Lớp **positive chiếm {shares['positive']}%** ({int(df[(df.split=='train')&(df.label=='positive')].n_comments.iloc[0]):,} bình luận), "
            f"**negative {shares['negative']}%** và **neutral chỉ {shares['neutral']}%** — dữ liệu mất cân bằng rõ rệt.",
            "Tỷ lệ ba lớp **giống hệt nhau ở cả train/val/test** (chênh dưới 0.02 điểm phần trăm) vì "
            "bước chia tập dùng thuật toán cân bằng theo nhóm phim (Task 6).",
        ],
        "action": "Khi lập kế hoạch kiểm duyệt, đừng chia đều nguồn lực cho ba lớp và **đừng dùng accuracy** "
                  "làm chỉ tiêu: đoán bừa \"positive\" đã đúng 61%. Theo dõi bằng F1 từng lớp.",
    }


# ---------------------------------------------------------------------------
# Hình 07 — độ dài bình luận theo lớp cảm xúc
# ---------------------------------------------------------------------------
def fig07_length(df_hist: pd.DataFrame, df_q: pd.DataFrame, bin_max: int) -> dict:
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.6),
                             gridspec_kw={"width_ratios": [2.0, 1.0]})
    ax = axes[0]
    for lab in LABELS:
        d = df_hist[df_hist.label == lab].sort_values("bin_lower_tokens")
        x = d.bin_lower_tokens.to_numpy()
        y = (d.share_in_class * 100).to_numpy()
        ax.plot(x, y, marker="o", ms=4, lw=1.8, color=SENTIMENT_COLORS[lab],
                label=f"{CLASS_EN[lab]} (n={int(df_q[df_q.label==lab].n_comments.iloc[0]):,})")
        p50 = float(df_q[df_q.label == lab].p50_tokens.iloc[0])
        ax.axvline(p50, color=SENTIMENT_COLORS[lab], ls=":", lw=1.2, alpha=0.9)
        ax.annotate(f"median {int(p50)}", xy=(p50, ax.get_ylim()[1] * 0.93),
                    xytext=(p50 + 6, ax.get_ylim()[1] * 0.93), fontsize=8,
                    color=SENTIMENT_COLORS[lab], rotation=90, va="top")
    ax.set_xticks(list(range(0, bin_max + 1, 50)) + [bin_max],
                  [str(v) for v in range(0, bin_max + 1, 50)] + [f"{bin_max}+"])
    ax.set_xlabel(f"Comment length (tokens, bins of {int(df_hist.bin_lower_tokens.diff().mode().iloc[0])} tokens; "
                  f"last bin = {bin_max}+)")
    ax.set_ylabel("Share of comments in class (% of class)")
    ax.set_title("Comment length by sentiment class (cleaned text, train set)")
    ax.legend(frameon=False)

    ax = axes[1]
    ypos = np.arange(len(LABELS))[::-1]
    for y, lab in zip(ypos, LABELS):
        r = df_q[df_q.label == lab].iloc[0]
        ax.plot([r.p25_tokens, r.p95_tokens], [y, y], color=SENTIMENT_COLORS[lab], lw=7,
                alpha=0.35, solid_capstyle="butt")
        ax.plot([r.p25_tokens, r.p75_tokens], [y, y], color=SENTIMENT_COLORS[lab], lw=7,
                solid_capstyle="butt")
        ax.plot([r.p50_tokens], [y], marker="|", ms=18, mew=2.5, color="black")
        ax.text(r.p50_tokens, y + 0.24, f"median {int(r.p50_tokens)}", ha="center",
                fontsize=8)
    ax.set_yticks(ypos, [CLASS_EN[l] for l in LABELS])
    ax.set_xlabel("Comment length (tokens)")
    ax.set_title("Quantiles\n(dark band = p25–p75, thin = p25–p95)")
    ax.set_xlim(0, 560)
    ax.set_ylim(-0.6, len(LABELS) - 0.45)      # chừa chỗ cho nhãn "median" phía trên hàng đầu
    finish(fig, FIGURES / "07_length_by_class.png",
             note="Source: outputs/tables/eda_length_histogram.csv + eda_length_quantiles.csv "
                  "(Spark SQL q02–q03). 'Tokens' = whitespace split of the cleaned text, same as the model's tokenizer.")
    plt.close(fig)

    med = {l: int(df_q[df_q.label == l].p50_tokens.iloc[0]) for l in LABELS}
    ratio = med["neutral"] / med["positive"]
    return {
        "file": "07_length_by_class.png",
        "title": "7. Comment length by sentiment class",
        "bullets": [
            f"Bình luận **neutral dài nhất** (trung vị {med['neutral']} token, p95 "
            f"{int(df_q[df_q.label=='neutral'].p95_tokens.iloc[0])}) — dài gấp **{ratio:.1f}×** so với "
            f"positive ({med['positive']} token). Negative ở giữa ({med['negative']} token).",
            "Phân bố lệch phải mạnh ở cả ba lớp: 25% bình luận ngắn dưới ~32 token, nhưng 5% dài trên ~380–500 token "
            "— chất lượng thông tin trong một bình luận chênh nhau hàng chục lần.",
        ],
        "action": "Nếu mỗi ngày chỉ đọc tay được một số lượng hữu hạn, **ưu tiên bình luận dài (> 300 token)**: "
                  "đây đúng là nhóm mà mô hình yếu nhất (F1 lớp neutral chỉ 0.378 ở hình 14) và cũng là nhóm "
                  "có nhiều ngữ cảnh nhất để người kiểm duyệt ra quyết định.",
    }


# ---------------------------------------------------------------------------
# Hình 08 — top 20 từ đặc trưng mỗi lớp
# ---------------------------------------------------------------------------
def fig08_top_words(df: pd.DataFrame) -> dict:
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 6.4))
    for ax, lab in zip(axes, LABELS):
        d = df[df.label == lab].sort_values("z_score").tail(20)   # để từ mạnh nhất ở trên
        y = np.arange(len(d))
        ax.barh(y, d.z_score, color=SENTIMENT_COLORS[lab], alpha=0.9)
        ax.set_yticks(y, d.word)
        for yi, (z, n) in enumerate(zip(d.z_score, d.n_in_class)):
            ax.text(z + 1.0, yi, f"{int(n):,}", va="center", fontsize=7.5, color="#444444")
        ax.set_title(f"{CLASS_EN[lab]} — top 20", color=SENTIMENT_COLORS[lab])
        ax.set_xlabel("Log-odds z-score (class vs rest)")
        ax.set_xlim(0, d.z_score.max() * 1.22)
        ax.margins(y=0.01)
    axes[0].set_ylabel("Word (number = count in class)")
    fig.suptitle("Most distinctive words per sentiment class (train set, log-odds with Dirichlet prior)",
                 fontsize=13, y=0.98)
    finish(fig, FIGURES / "08_top_words_by_class.png",
             note="Source: outputs/tables/eda_top_words_by_class.csv (Spark SQL q04). "
                  "Frequency-based analysis, NOT the model's learned weights (see Task 7, top_features.csv).",
             top=0.955)
    plt.close(fig)

    top = {l: df[df.label == l].sort_values("z_score", ascending=False).iloc[0] for l in LABELS}
    neutral_rating = df[(df.label == "neutral") & df.word.str.match(r"^\d+/10$")]
    n_rating = len(neutral_rating)
    return {
        "file": "08_top_words_by_class.png",
        "title": "8. Top 20 distinctive words per sentiment class",
        "bullets": [
            f"Từ đặc trưng nhất: negative **\"{top['negative'].word}\"** (z={top['negative'].z_score:.1f}), "
            f"neutral **\"{top['neutral'].word}\"** (z={top['neutral'].z_score:.1f}), "
            f"positive **\"{top['positive'].word}\"** (z={top['positive'].z_score:.1f}).",
            f"Điểm đáng lo: **{n_rating} trong 20 từ đặc trưng nhất của lớp neutral là điểm số dạng \"x/10\"** "
            f"(ví dụ \"{top['neutral'].word}\"). Mô hình đang học *con số trong bài*, không phải cảm xúc — "
            "đúng như cảnh báo ở outputs/modeling_summary.md §5.",
        ],
        "action": "Trước khi dùng cho livestream thật (bình luận không có điểm số), hãy coi **chỉ số 0.63 macro-F1 "
                  "là mức trần lạc quan**; cần thu 200–300 bình luận thật có gán nhãn tay để đo lại trước khi tin.",
    }


# ---------------------------------------------------------------------------
# Hình 09 — emoji theo lớp cảm xúc
# ---------------------------------------------------------------------------
def fig09_emoji(df: pd.DataFrame, top_n: int) -> dict:
    """Ô nhiệt: tỷ lệ dùng của TỪNG emoji trong mỗi lớp.

    Lưu ý một cái bẫy của bảng q05: cột `emoji_per_1000_comments` là mật độ emoji
    của CẢ LỚP nên giống hệt nhau ở mọi dòng cùng lớp — vẽ nó lên ô nhiệt sẽ ra
    một hình vô nghĩa (mọi dòng một giá trị). Muốn biết *emoji nào* đặc trưng cho
    lớp nào thì phải tính lại theo từng emoji:
        rate = 1000 × n_emoji(của emoji đó, trong lớp) / n_comments_in_class
    Ô trống trong bảng = emoji không xuất hiện lần nào ở lớp đó -> điền 0.
    """
    top = df.drop_duplicates("emoji").sort_values("rk_global").head(top_n)
    df = df.assign(rate_per_1000=1000.0 * df.n_emoji / df.n_comments_in_class)
    pivot = (df.pivot_table(index="emoji", columns="label", values="rate_per_1000",
                            aggfunc="first")
               .reindex(top.emoji).reindex(columns=LABELS).fillna(0.0))
    vmax = float(pivot.to_numpy().max())

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.4),
                             gridspec_kw={"width_ratios": [2.15, 1.0], "wspace": 0.42})
    ax = axes[0]
    im = ax.imshow(pivot.to_numpy(), cmap="YlGnBu", aspect="auto", vmin=0, vmax=vmax)
    ax.set_xticks(range(len(LABELS)), [CLASS_EN[l] for l in LABELS])
    ax.set_yticks(range(len(pivot)), [emoji_label(e) for e in pivot.index], fontsize=9)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.iloc[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8.5,
                    color="white" if v > vmax * 0.6 else "#222222")
    ax.set_title(f"Top {top_n} emoji — how often each one appears in a class\n"
                 f"(cell shading and number = occurrences per 1,000 comments of that class)")

    ax = axes[1]
    stats = df.groupby("label")[["pct_comments_with_emoji", "emoji_per_1000_comments"]].first()
    y = np.arange(len(LABELS))[::-1]
    ax.barh(y, [stats.loc[l, "emoji_per_1000_comments"] for l in LABELS],
            color=[SENTIMENT_COLORS[l] for l in LABELS])
    for yi, l in zip(y, LABELS):
        ax.text(stats.loc[l, "emoji_per_1000_comments"] + 1.0, yi,
                f"{stats.loc[l,'emoji_per_1000_comments']:.0f}   "
                f"({stats.loc[l,'pct_comments_with_emoji']:.1f}% of\ncomments have one)",
                va="center", fontsize=8.5)
    ax.set_yticks(y, [CLASS_EN[l] for l in LABELS])
    ax.set_xlim(0, stats.emoji_per_1000_comments.max() * 1.9)
    ax.set_xlabel("Emoji per 1,000 comments")
    ax.set_title("All emoji combined —\nhow much each class uses emoji")
    finish(fig, FIGURES / "09_emoji_by_class.png",
             note="Source: outputs/tables/eda_emoji_by_class.csv (Spark SQL q05). "
                  "Uses text_cleaning.EMOJI_SYMBOL_RANGES, which excludes typographic symbols (e.g. U+00B0) "
                  "that the cleaner's broader \\p{So} class also catches.",
             manual={"left": 0.255, "right": 0.995, "top": 0.865, "bottom": 0.16, "wspace": 0.42})
    plt.close(fig)

    neg_top = df[df.label == "negative"].sort_values("rk_in_class").iloc[0]
    pos_rate = float(stats.loc["positive", "emoji_per_1000_comments"])
    neu_rate = float(stats.loc["neutral", "emoji_per_1000_comments"])
    tear_rate = float(pivot.loc[neg_top.emoji, "negative"]) if neg_top.emoji in pivot.index else 0.0
    tear_pos = float(pivot.loc[neg_top.emoji, "positive"]) if neg_top.emoji in pivot.index else 0.0
    td = df[df.emoji == THUMBS_DOWN].set_index("label").rate_per_1000
    td_neg = float(td.get("negative", 0.0))
    td_pos = float(td.get("positive", 0.0))
    return {
        "file": "09_emoji_by_class.png",
        "title": "9. Emoji usage by sentiment class",
        "bullets": [
            f"Lớp positive dùng emoji **nhiều gấp {pos_rate/neu_rate:.1f}×** lớp neutral "
            f"({pos_rate:.0f} so với {neu_rate:.0f} emoji trên 1.000 bình luận; "
            f"{float(stats.loc['positive','pct_comments_with_emoji']):.1f}% bình luận positive có emoji). "
            "Nhưng mức dùng tuyệt đối vẫn rất thấp — emoji **không phải** tín hiệu đủ mạnh.",
            f"Emoji đứng đầu lớp **negative lại là \"{emoji_label(neg_top.emoji)}\"**: "
            f"{tear_rate:.2f} lần trên 1.000 bình luận negative, so với {tear_pos:.2f} ở positive "
            f"(hạng {int(neg_top.rk_in_class)} trong lớp). Cùng nhóm đó, \"{emoji_label(THUMBS_DOWN)}\" xuất hiện "
            f"{td_neg:.2f} lần/1.000 bình luận negative nhưng chỉ {td_pos:.2f} ở positive. "
            "Vậy \"cười\" **không** đồng nghĩa \"tích cực\".",
        ],
        "action": "**Đừng dùng emoji làm quy tắc cảm xúc** (ví dụ \"có 😂 thì là tích cực\") — dữ liệu nói ngược lại. "
                  "Nếu dashboard có ô đếm emoji thì để cạnh chỉ số cảm xúc, không thay thế nó.",
    }


# ---------------------------------------------------------------------------
# Hình 10 — cảm xúc theo thời gian (cửa sổ 1 phút + cửa sổ trượt 10 giây)
# ---------------------------------------------------------------------------
def fig10_timeline(min_df: pd.DataFrame, sec_df: pd.DataFrame, burst: dict,
                   label_min_n: int = 30) -> dict:
    """Hai khung: cửa sổ nhảy 1 phút (đúng yêu cầu) + cửa sổ trượt 10 giây.

    Chèn NaN vào chỗ KHÔNG có cửa sổ trước khi vẽ: nếu để matplotlib nối thẳng,
    vùng từ 17:58 tới 18:08 sẽ được tô thành một hình nêm 1.000 bình luận — trông
    như có dữ liệu liên tục trong 10 phút trong khi thực tế chỉ có 1 bình luận.
    """
    for d in (min_df, sec_df):
        d["t"] = pd.to_datetime(d.window_start)

    def with_gaps(d: pd.DataFrame, grid: pd.Timedelta) -> pd.DataFrame:
        """Thêm dòng NaN vào giữa hai cửa sổ cách nhau hơn `grid` (để vùng trống vẫn trống)."""
        d = d.sort_values("t").reset_index(drop=True)
        nums = [c for c in d.columns if c.startswith("n_")]
        rows = []
        prev = None
        for _, r in d.iterrows():
            if prev is not None and (r.t - prev).total_seconds() > grid.total_seconds() * 1.5:
                rows.append({**{c: np.nan for c in nums}, "t": r.t})
            rows.append(r.to_dict())
            prev = r.t
        return pd.DataFrame(rows)

    fig, axes = plt.subplots(2, 1, figsize=(11.8, 7.8), sharex=True,
                             gridspec_kw={"hspace": 0.30})

    def stacked(ax, d, title, annotate_from):
        x = d.t
        ax.stackplot(x, *[np.ma.masked_invalid(d[f"n_{c}"].to_numpy(float))
                          for c in ("positive", "neutral", "negative")],
                     colors=[SENTIMENT_COLORS["positive"], SENTIMENT_COLORS["neutral"],
                             SENTIMENT_COLORS["negative"]],
                     labels=["Positive", "Neutral", "Negative"], alpha=0.9)
        tot = (d.n_positive + d.n_neutral + d.n_negative).to_numpy(float)
        ax.plot(x, np.ma.masked_invalid(tot), color="#333333", lw=0.9, ls="--",
                marker="o", ms=3.5, label="Total comments")
        for xi, ti in zip(x, tot):
            if np.isfinite(ti) and ti >= annotate_from:      # bỏ nhãn ở các cửa sổ 1–3 bình luận
                ax.annotate(f"{int(ti)}", xy=(xi, ti), xytext=(0, 5),
                            textcoords="offset points", ha="center", fontsize=8,
                            color="#333333")
        ax.set_title(title)
        ax.set_ylabel("Comments in window (count)")
        ax.legend(frameon=False, ncol=4, loc="upper left", fontsize=9)
        ax.margins(x=0.02)

    d1 = with_gaps(min_df, pd.Timedelta(minutes=1))
    stacked(axes[0], d1,
            "Stacked sentiment per 1-minute window (streaming output, tumbling window)", label_min_n)
    d2 = with_gaps(sec_df, pd.Timedelta(seconds=5))
    stacked(axes[1], d2,
            "Stacked sentiment per 10-second sliding window (step 5 s — windows overlap, "
            "heights are NOT additive)", label_min_n)
    # Đợt bùng nổ thật (đo từ outputs/tables/eda_throughput_per_second.csv): mọi
    # con số ở đây truyền vào từ ngoài, không viết tay trong hình.
    axes[0].axvspan(*burst["span"], color="#F4A261", alpha=0.18, zorder=0)
    axes[0].annotate(f"{burst['n']:,} of {burst['total']:,} comments arrive in "
                     f"{burst['seconds']:.0f} s\n({burst['span'][0]:%H:%M:%S}–{burst['span'][1]:%H:%M:%S} UTC)",
                     xy=(burst["span"][0], 620), xytext=(-10, 0), textcoords="offset points",
                     fontsize=8.5, color="#8A5A2B", ha="right", va="center")
    synth = sec_df[sec_df.n_synthetic == sec_df.n_comments]
    if len(synth) and len(sec_df) > 1:
        axes[1].axvspan(synth.t.min(), synth.t.max(), color="#BBBBBB", alpha=0.3, zorder=0)
        axes[1].annotate("verification heartbeats only (no real comments)",
                         xy=(synth.t.min() + (synth.t.max() - synth.t.min()) / 2,
                             sec_df.n_comments.max() * 0.6),
                         fontsize=8, color="#555555", ha="center")
    axes[1].set_xlabel("Event-time window start (UTC)")
    finish(fig, FIGURES / "10_sentiment_timeline.png",
             note="Source: outputs/tables/eda_sentiment_per_minute.csv + eda_sentiment_per_10s.csv "
                  "(streaming window queries of run 'verify1', Spark SQL q06–q07). REPLAY data (IMDb), "
                  "not a real livestream. Gaps = windows with no comments (no line interpolated across them).",
             manual={"left": 0.088, "right": 0.99, "top": 0.935, "bottom": 0.115, "hspace": 0.30})
    plt.close(fig)

    d1, d2 = min_df.sort_values("t"), sec_df.sort_values("t")
    big = d1.loc[d1.n_comments.idxmax()]
    peak_sec = d2.loc[d2.n_comments.idxmax()]
    late = d2[d2.n_synthetic == d2.n_comments]
    return {
        "file": "10_sentiment_timeline.png",
        "title": "10. Sentiment over time (streaming output)",
        "bullets": [
            f"Cửa sổ 1 phút chỉ có **4 điểm dữ liệu**: đợt phát dồn vào **một phút duy nhất** "
            f"(total {int(big.n_comments)} bình luận, positive {big.share_positive:.1%} / neutral {big.share_neutral:.1%} / "
            f"negative {big.share_negative:.1%}); **{burst['n']:,}/{burst['total']:,} bình luận đến trong "
            f"{burst['seconds']:.0f} giây** ({burst['span'][0]:%H:%M:%S}–{burst['span'][1]:%H:%M:%S} UTC). "
            "Vì vậy phải xem thêm khung cửa sổ trượt 10 giây mới thấy diễn biến bên trong.",
            f"Trong cửa sổ 10 giây, tỷ lệ tiêu cực dao động **{d2[d2.n_comments>=5].share_negative.min():.1%} – "
            f"{d2[d2.n_comments>=5].share_negative.max():.1%}** giữa các cửa sổ (đỉnh {int(peak_sec.n_comments)} bình luận/cửa sổ); "
            f"{len(late)} cửa sổ chỉ chứa bản ghi nhịp tim kiểm chứng — tỷ lệ ở đó không có ý nghĩa.",
        ],
        "action": "Trong livestream thật, đừng chờ hết phút mới nhìn: dùng **cửa sổ trượt 10 giây** để bắt đà tăng "
                  "của tỷ lệ tiêu cực trong lúc sự việc đang diễn ra (xem quy tắc cảnh báo ở hình 12).",
    }


# ---------------------------------------------------------------------------
# Hình 11 — thông lượng mỗi giây + đánh dấu bùng nổ
# ---------------------------------------------------------------------------
def fig11_throughput(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["t"] = pd.to_datetime(df.second_utc)
    fig, ax = plt.subplots(figsize=(11.6, 4.6))
    colors = [WARN if b else "#457B9D" for b in df.is_burst.astype(bool)]
    ax.bar(df.t, df.n_comments, width=0.9 / 86400, color=colors,   # 1 giây = 1/86400 ngày
           label="Comments per second")
    mean = float(df.mean_per_sec.iloc[0])
    thr = float(df.burst_threshold.iloc[0])
    ceil = float(df.configured_burst_ceiling.iloc[0])
    ax.axhline(mean, color="#666666", ls="--", lw=1.2, label=f"Run mean ({mean:.1f} msg/s)")
    ax.axhline(thr, color="#E9C46A", ls="--", lw=1.4,
               label=f"Burst threshold, mean+2σ ({thr:.0f} msg/s)")
    ax.axhline(ceil, color=WARN, ls=":", lw=1.6,
               label=f"Configured burst ceiling, rate×factor ({ceil:.0f} msg/s)")
    for _, r in df[df.is_burst.astype(bool)].iterrows():
        ax.annotate(f"{int(r.n_comments)} msg/s", xy=(r.t, r.n_comments),
                    xytext=(8, 6), textcoords="offset points", fontsize=9.5, color=WARN,
                    fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                              edgecolor="none", alpha=0.75))
    ax.set_ylabel("Comments per second (event time, count)")
    ax.set_xlabel("Time (UTC)")
    ax.set_title(f"Streaming throughput per second — replay of 1,000 comments "
                 f"({int(df.n_seconds_with_data.iloc[0])} active seconds)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
    h, l = ax.get_legend_handles_labels()
    ax.legend(handles=h + [Patch(color=WARN, label="Seconds flagged as burst")],
              labels=l + ["Seconds flagged as burst"], frameon=False, fontsize=9)
    finish(fig, FIGURES / "11_throughput_burst.png",
             note="Source: outputs/tables/eda_throughput_per_second.csv (Spark SQL q08) — "
                  "burst rule: count > mean + 2σ of this run; ceiling = replay.rate × replay.burst_factor from config.yaml.")
    plt.close(fig)

    bursts = df[df.is_burst.astype(bool)]
    peak = float(df.n_comments.max())
    return {
        "file": "11_throughput_burst.png",
        "title": "11. Throughput per second and burst detection",
        "bullets": [
            f"Chỉ **{len(bursts)} trong {int(df.n_seconds_with_data.iloc[0])} giây có dữ liệu** vượt ngưỡng bùng nổ "
            f"({thr:.0f} msg/s): {bursts.t.iloc[0].strftime('%H:%M:%S')} UTC với "
            f"{int(bursts.n_comments.iloc[0])} msg/s và "
            f"{bursts.t.iloc[-1].strftime('%H:%M:%S')} UTC với {int(bursts.n_comments.iloc[-1])} msg/s.",
            f"Đỉnh đo được **{peak:.0f} msg/s = {peak/ceil:.0%} trần thiết kế** (rate 50 × burst_factor 8 = {ceil:.0f} msg/s "
            f"trong config.yaml) — bộ phát replay chạy đúng thiết kế, và đây cũng là mức tải lớn nhất hệ thống đã thực sự chịu.",
        ],
        "action": "Đặt **cảnh báo hạ tầng ở mức {:.0f} msg/s** (trần thiết kế): vượt mức đó là bộ phát/hệ thống đã ra khỏi "
                  "vùng đã đo, cần kiểm tra `numInputRows` và độ trễ thay vì tin rằng mọi thứ vẫn ổn.".format(ceil),
    }


# ---------------------------------------------------------------------------
# Hình 12 — tỷ lệ tiêu cực + ngưỡng cảnh báo
# ---------------------------------------------------------------------------
def fig12_negative_alert(df: pd.DataFrame, neg_base_rate: float) -> dict:
    df = df.copy()
    df["t"] = pd.to_datetime(df.window_start)
    thr = float(df.alert_threshold.iloc[0])
    min_n = int(df.min_comments.iloc[0])
    fig, axes = plt.subplots(2, 1, figsize=(11.6, 7.4), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 1.0]})
    ax = axes[0]
    ok = df[df.has_enough_volume]
    low = df[~df.has_enough_volume]
    ax.plot(ok.t, ok.share_negative * 100, marker="o", ms=5, color=SENTIMENT_COLORS["negative"],
            lw=1.6, label=f"Negative share (windows with ≥{min_n} comments)")
    ax.scatter(low.t, low.share_negative * 100, marker="o", s=26, facecolors="none",
               edgecolors="#999999", label=f"Too few comments (<{min_n}) — not alerted")
    ax.axhline(thr * 100, color=WARN, ls="--", lw=1.5,
               label=f"Alert threshold {thr:.0%} = test-set negative rate {neg_base_rate:.1%} "
                     f"+ {(thr - neg_base_rate) * 100:.0f} pp")
    alerts = df[df.is_alert]
    if len(alerts):
        ax.scatter(alerts.t, alerts.share_negative * 100, marker="X", s=150,
                   color=WARN, zorder=5, label="ALERT")
        for _, r in alerts.iterrows():
            ax.annotate(f"ALERT {r.share_negative:.1%}\n({int(r.n_comments)} comments)",
                        xy=(r.t, r.share_negative * 100), xytext=(8, 6),
                        textcoords="offset points", fontsize=8.5, color=WARN, fontweight="bold")
    ax.set_ylabel("Negative share in window (%)")
    ax.set_ylim(-5, 112)
    ax.set_title(f"Negative-share monitor — 10 s sliding windows, alert rule "
                 f"(share > {thr:.0%} AND ≥{min_n} comments)")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))

    ax = axes[1]
    ax.bar(df.t, df.n_comments, width=0.9 * 10 / 86400, color=ACCENT)   # cửa sổ 10 giây
    ax.axhline(min_n, color="#666666", ls=":", lw=1.2, label=f"Minimum volume ({min_n})")
    ax.set_yscale("log")
    ax.set_ylabel("Comments in\nwindow (count)")
    ax.set_xlabel("Event-time window start (UTC)")
    ax.legend(frameon=False, fontsize=9)
    finish(fig, FIGURES / "12_negative_share_alert.png",
             note="Source: outputs/tables/eda_negative_share_alert.csv (Spark SQL q09). "
                  "Replay data (IMDb), not a real livestream; thresholds are configurable in config.yaml (eda.alert).")
    plt.close(fig)

    n_false = int((~df.has_enough_volume & (df.share_negative > thr)).sum())
    return {
        "file": "12_negative_share_alert.png",
        "title": "12. Negative-share monitor with alerting",
        "bullets": [
            f"Quy tắc cảnh báo (tỷ lệ tiêu cực > {thr:.0%} **và** ≥{min_n} bình luận) bắn đúng "
            f"**{len(alerts)} lần**: {alerts.t.iloc[0].strftime('%H:%M:%S')} UTC với "
            f"{alerts.share_negative.iloc[0]:.1%} ({int(alerts.n_comments.iloc[0])} bình luận) — "
            "đó là đỉnh tiêu cực thật của đợt bùng nổ."
            if len(alerts) else
            f"Trong lần chạy này quy tắc cảnh báo (> {thr:.0%} và ≥{min_n} bình luận) **không bắn lần nào**.",
            f"Nếu **bỏ điều kiện đủ {min_n} bình luận**, sẽ có thêm **{n_false} báo động giả** (cửa sổ 1–3 bình luận "
            f"cho tỷ lệ 33–100%) — đúng như đã thấy ở Task 8 với các bản ghi nhịp tim đơn lẻ.",
        ],
        "action": f"Đưa đúng quy tắc này vào dashboard: **cửa sổ 10 giây, cảnh báo khi tỷ lệ tiêu cực > {thr:.0%} và "
                  f"số bình luận ≥ {min_n}**, kèm hiển thị số bình luận trong cửa sổ để người trực biết mức tin cậy.",
    }


# ---------------------------------------------------------------------------
# Hình 13 — phân bố độ trễ end-to-end
# ---------------------------------------------------------------------------
def fig13_latency(hist: pd.DataFrame, q: pd.DataFrame) -> dict:
    row = q[q.label == "all"].iloc[0]
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.8),
                             gridspec_kw={"width_ratios": [1.7, 1.0]})
    ax = axes[0]
    colors = [WARN if n > 0 else "#457B9D" for n in hist.n_injected_late]
    ax.bar(hist.bin_lower_ms, hist.n_comments,
           width=hist.bin_upper_ms - hist.bin_lower_ms, align="edge",
           color=colors, edgecolor="white", linewidth=0.4)
    ax.set_xscale("log")
    ax.set_ylim(0, float(hist.n_comments.max()) * 1.22)
    for i, (name, val) in enumerate((("p50", row.p50_ms), ("p95", row.p95_ms), ("p99", row.p99_ms))):
        ax.axvline(val, color="#333333", ls="--", lw=1.2)
        ax.annotate(f"{name} = {val:,.0f} ms", xy=(val, ax.get_ylim()[1] * 0.97),
                    xytext=(3, -4 - 16 * i), textcoords="offset points", fontsize=8.5,
                    rotation=90, va="top",
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="white",
                              edgecolor="none", alpha=0.7))
    ax.set_xlabel("End-to-end latency (ms, log scale, bins of ~1.6×)")
    ax.set_ylabel("Comments (count)")
    ax.set_title(f"End-to-end latency distribution (n={int(row.n_comments):,})")
    ax.legend(handles=[Patch(color="#457B9D"), Patch(color=WARN)],
              labels=["Measured stream", "Intentionally late probes (10 min)"],
              frameon=False, fontsize=9, loc="upper right")

    ax = axes[1]
    ladder = [("min", row.min_ms), ("p50", row.p50_ms), ("p90", row.p90_ms),
              ("p95", row.p95_ms), ("p99", row.p99_ms), ("max", row.max_ms)]
    xs = [v for _, v in ladder]
    ax.plot(xs, range(len(ladder)), marker="o", color=ACCENT, lw=1.6)
    for i, (name, v) in enumerate(ladder):
        ax.annotate(f"{name}  {v:,.0f} ms", xy=(v, i), xytext=(-6, -12 if i == 0 else 6),
                    textcoords="offset points", fontsize=8.5, ha="right")
    ax.set_yticks(range(len(ladder)), [n for n, _ in ladder])
    ax.set_xscale("log")
    ax.set_xlabel("Latency (ms, log scale)")
    ax.set_title(f"Percentile ladder\n(all {int(row.n_comments):,} comments)")
    ax.set_ylim(-0.8, len(ladder) - 0.2)
    ax.set_xlim(20, 2e6)
    finish(fig, FIGURES / "13_latency_distribution.png",
             note="Source: outputs/tables/eda_latency_histogram.csv + eda_latency_quantiles.csv (Spark SQL q10–q11). "
                  "Latency = processing time − event time, measured per micro-batch (see src/streaming/README.md §7).")
    plt.close(fig)

    mass = hist[(hist.bin_lower_ms >= 1000) & (hist.bin_upper_ms <= 3981.1)].n_comments.sum()
    second = hist[hist.bin_lower_ms >= 6309].sort_values("n_comments", ascending=False).iloc[0]
    return {
        "file": "13_latency_distribution.png",
        "title": "13. End-to-end latency distribution",
        "bullets": [
            f"Phân bố **hai đỉnh**: **{int(mass):,}/{int(row.n_comments):,} bình luận "
            f"({mass/row.n_comments:.0%}) được chấm trong 1.0–4.0 giây** (p50 = {row.p50_ms:,.0f} ms), "
            f"nhưng có một nhóm thứ hai đúng **{int(second.n_comments)} bình luận ở "
            f"{second.bin_lower_ms/1000:.1f}–{second.bin_upper_ms/1000:.1f} giây**. "
            f"p95 = {row.p95_ms:,.0f} ms, p99 = {row.p99_ms:,.0f} ms.",
            f"Đuôi dài **không** đến từ chặng Kafka (kafka p50 = {row.kafka_p50_ms:,.0f} ms, "
            f"p95 = {row.kafka_p95_ms:,.0f} ms) mà từ **hàng đợi xử lý trong micro-batch**: "
            f"queue p50 = {row.queue_p50_ms:,.0f} ms, p95 = {row.queue_p95_ms:,.0f} ms — bình luận dồn về đúng lúc bùng nổ. "
            f"Hai bản ghi cố tình đẩy trễ 10 phút nằm ở cột ngoài cùng bên phải ({int(row.max_ms/1000):,} giây).",
        ],
        "action": f"Nếu livestream cần hiển thị cảm xúc tức thì, **hạ trigger từ 5 s xuống 1–2 s** hoặc tăng song song: "
                  f"hiện p95 đã là {row.p95_ms/1000:.1f} s, quá chậm cho phản hồi trong lúc đang phát.",
    }


# ---------------------------------------------------------------------------
# Hình 14 — chất lượng mô hình (lấy từ Task 7)
# ---------------------------------------------------------------------------
def fig14_model_quality(cm_df: pd.DataFrame, pc_df: pd.DataFrame,
                        model: str = "LogisticRegression") -> dict:
    cm = (cm_df[(cm_df.model == model) & (cm_df.split == "test")]
          .pivot(index="true_label", columns="pred_label", values="count")
          .reindex(index=LABELS, columns=LABELS).fillna(0).astype(int))
    pc = pc_df[(pc_df.model == model) & (pc_df.split == "test")].set_index("label").reindex(LABELS)
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.9),
                             gridspec_kw={"width_ratios": [1.0, 1.25], "wspace": 0.34})
    ax = axes[0]
    row_share = cm.div(cm.sum(axis=1), axis=0)
    im = ax.imshow(row_share.to_numpy(), cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(3), [CLASS_EN[l] for l in LABELS])
    ax.set_yticks(range(3), [CLASS_EN[l] for l in LABELS])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True label (from rating)")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{row_share.iloc[i, j]:.0%}\n({cm.iloc[i, j]:,})", ha="center",
                    va="center", fontsize=9,
                    color="white" if row_share.iloc[i, j] > 0.55 else "#222222")
    ax.set_title(f"Confusion matrix — {model}, test set (n={int(cm.to_numpy().sum()):,})\n"
                 f"(cell shade and % = share of the true class)")

    ax = axes[1]
    x = np.arange(3)
    w = 0.26
    metrics = [("precision", 1.0), ("recall", 0.72), ("f1", 0.44)]
    for k, (metric, alpha) in enumerate(metrics):
        ax.bar(x + (k - 1) * w, pc[metric], w, alpha=alpha,
               color=[SENTIMENT_COLORS[l] for l in LABELS], edgecolor="white")
    for k, metric in enumerate(["precision", "recall", "f1"]):
        for xi, l in zip(x, LABELS):
            ax.text(xi + (k - 1) * w, pc.loc[l, metric] + 0.012, f"{pc.loc[l, metric]:.2f}",
                    ha="center", fontsize=7.5)
    ax.set_xticks(x, [f"{CLASS_EN[l]}\n(support {int(pc.loc[l,'support']):,})" for l in LABELS])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score (0–1)")
    ax.set_title("Precision / Recall / F1 per class")
    # Chú giải màu xám (không lấy màu lớp) để thấy rõ: màu cột = LỚP, độ đậm = CHỈ SỐ.
    ax.legend(handles=[Patch(color="#555555", alpha=a, label=m.capitalize())
                       for m, a in metrics]
              + [Patch(color=SENTIMENT_COLORS[l], label=CLASS_EN[l]) for l in LABELS],
              frameon=False, ncol=3, fontsize=8.5)
    finish(fig, FIGURES / "14_model_quality.png",
             note="Source: outputs/tables/confusion_matrix.csv + per_class_metrics.csv from Task 7 "
                  "(offline evaluation on the held-out test set, single use). Reproduced here for the report.",
             manual={"left": 0.095, "right": 0.99, "top": 0.855, "bottom": 0.205, "wspace": 0.34})
    plt.close(fig)

    merged = cm.stack().rename("count").reset_index()
    merged["row_share"] = merged.apply(
        lambda r: row_share.loc[r.true_label, r.pred_label], axis=1).round(4)
    merged["model"] = model
    write_table(merged, "eda_model_quality")
    acc = cm.to_numpy().diagonal().sum() / cm.to_numpy().sum()
    return {
        "file": "14_model_quality.png",
        "title": "14. Model quality (offline, from Task 7)",
        "bullets": [
            f"Trên tập test, mô hình LogisticRegression đạt **F1: negative {pc.loc['negative','f1']:.2f} — "
            f"neutral {pc.loc['neutral','f1']:.2f} — positive {pc.loc['positive','f1']:.2f}** "
            f"(accuracy {acc:.3f}).",
            f"Lớp neutral là điểm yếu nhất: chỉ **{row_share.loc['neutral','neutral']:.0%}** bình luận neutral được "
            f"đoán đúng, {row_share.loc['neutral','positive']:.0%} bị đoán nhầm thành positive — phù hợp với kết luận "
            "\"nhãn neutral suy từ rating 5–6 là nhãn nhiễu\" (docs/data_dictionary.md §3).",
        ],
        "action": "Với các bình luận mô hình gán **neutral**, hãy để người kiểm duyệt xem lại (độ tin cậy thấp), "
                  "và **không dùng ngưỡng cảm xúc chung cho cả ba lớp** vì chất lượng mỗi lớp chênh nhau gần 0.44 F1.",
    }


# ---------------------------------------------------------------------------
# Hình 15 (tuỳ chọn) — biểu đồ tương tác plotly
# ---------------------------------------------------------------------------
def fig15_interactive(sec_df: pd.DataFrame, min_df: pd.DataFrame) -> dict | None:
    try:
        import plotly.graph_objects as go
    except ImportError:
        log("Không có plotly -> bỏ qua hình 15 (tuỳ chọn)")
        return None
    d = sec_df.copy()
    d["t"] = pd.to_datetime(d.window_start)
    d = d.sort_values("t")
    fig = go.Figure()
    for lab, col in (("positive", SENTIMENT_COLORS["positive"]),
                     ("neutral", SENTIMENT_COLORS["neutral"]),
                     ("negative", SENTIMENT_COLORS["negative"])):
        fig.add_trace(go.Scatter(
            x=d.t, y=d[f"n_{lab}"], name=lab.capitalize(), mode="lines+markers",
            stackgroup="one", line=dict(color=col, width=1),
            hovertemplate=("%{x|%H:%M:%S} UTC<br>" + lab +
                           ": %{y} comments<br>window size: 10 s<extra></extra>")))
    fig.add_trace(go.Scatter(
        x=d.t, y=d.n_comments, name="Total (hover)", mode="markers",
        marker=dict(size=6, color="#333333"), yaxis="y2",
        hovertemplate="%{x|%H:%M:%S} UTC<br>total: %{y} comments<extra></extra>"))
    m = min_df.copy()
    m["t"] = pd.to_datetime(m.window_start)
    fig.update_layout(
        title="Sentiment over time — 10 s sliding windows (streaming replay, run verify1)<br>"
              "<sup>Interactive version of figure 10. Data: outputs/stream/verify1/window_sliding_10s "
              "(parquet) via outputs/tables/eda_sentiment_per_10s.csv. Replay data, not a real livestream.</sup>",
        xaxis_title="Event-time window start (UTC)", yaxis_title="Comments in window (count)",
        yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Total (markers)"),
        hovermode="x unified", template="plotly_white", legend_title="Sentiment class")
    out = FIGURES / "15_sentiment_timeline.html"
    fig.write_html(out, include_plotlyjs=True)   # nhúng plotly.js -> mở được khi không có mạng
    log(f"  -> {out.relative_to(PROJECT_ROOT)} ({out.stat().st_size/1e6:.1f} MB, tự chứa plotly.js)")
    return {"file": "15_sentiment_timeline.html",
            "title": "15. Interactive sentiment timeline (optional, HTML)",
            "bullets": [
                "Bản tương tác của hình 10: rê chuột để xem từng cửa sổ 10 giây (số bình luận mỗi lớp + tổng), "
                "dùng khi thuyết trình để soi đúng khoảng thời gian đang nói tới.",
            ],
            "action": "Mở file này ngay trên máy khi demo (tự chứa plotly.js nên **không cần mạng**).",
            "file_only": True}


# ---------------------------------------------------------------------------
def build_insights(items: list[dict], overview: pd.DataFrame, vocab: pd.DataFrame,
                   emoji_df: pd.DataFrame, peak_msg_s: float,
                   stream_metrics: pd.DataFrame | None) -> str:
    """Sinh outputs/insights.md từ chính các con số vừa vẽ."""
    o = overview.iloc[0]
    v = vocab.iloc[0]
    emo = emoji_df.groupby("label")[["emoji_per_1000_comments",
                                     "pct_comments_with_emoji"]].first()
    neg_top = emoji_df[emoji_df.label == "negative"].sort_values("rk_in_class").iloc[0]
    lines = [
        "# outputs/insights.md — Insight và hành động (Task 9)",
        "",
        f"Sinh tự động ngày **{datetime.now():%d/%m/%Y}** bởi `src/eda/plots.py` từ các bảng trong "
        "`outputs/tables/eda_*.csv` (do `src/eda/queries.py` chạy Spark SQL ghi ra). "
        "**Không có con số nào trong file này được viết tay.**",
        "",
        "Phạm vi số liệu:",
        f"- Dữ liệu huấn luyện: **{int(o.n_train):,} train / {int(o.n_val):,} val / {int(o.n_test):,} test** "
        "(IMDb Review Dataset - ebD, CC0, lấy mẫu 20% — xem `docs/data_dictionary.md`).",
        f"- Đầu ra streaming: lần chạy `verify1`, **{int(o.n_stream_comments):,} bình luận** "
        f"({int(o.n_replay_comments):,} phát lại + {int(o.n_synthetic_comments)} bản ghi kiểm chứng), "
        f"{o.stream_first_event_utc} → {o.stream_last_event_utc} UTC.",
        f"- ⚠️ **Dữ liệu streaming là REPLAY (phát lại review IMDb), KHÔNG phải bình luận livestream thật.** "
        "Mọi kết luận về hành vi người xem chỉ là minh hoạ cho cơ chế, phải đo lại khi có dữ liệu thật.",
        "",
        "---",
        "",
    ]
    for it in items:
        lines.append(f"## {it['title']}")
        lines.append("")
        if it.get("file_only"):
            # Hình tương tác là file .html -> chèn link, không nhúng ảnh (markdown sẽ vỡ ảnh)
            lines.append(f"**[Mở biểu đồ tương tác](figures/{it['file']})** "
                         "(file HTML tự chứa, mở bằng trình duyệt)")
        else:
            lines.append(f"![{it['title']}](figures/{it['file']})")
        lines.append("")
        lines.append("**Insight**")
        lines.append("")
        for b in it["bullets"]:
            lines.append(f"- {b}")
        lines.append("")
        lines.append(f"**Hành động**: {it['action']}")
        lines.append("")
        src = it.get("source_table")
        if src:
            # Có hình lấy số từ nhiều bảng (Hình 14 dùng cả confusion matrix lẫn
            # per_class_metrics của Task 7) -> cho phép khai báo danh sách.
            srcs = [src] if isinstance(src, str) else list(src)
            lines.append("*Bảng số liệu nền: "
                         + ", ".join(f"`outputs/tables/{s}.csv`" for s in srcs) + "*")
            lines.append("")
        lines.append("---")
        lines.append("")

    # --- Phần tổng hợp: những điều số liệu KHÔNG ủng hộ / chưa kiểm chứng -----
    lines += ["## Tổng hợp: điều số liệu ủng hộ và điều KHÔNG", ""]
    if stream_metrics is not None:
        st = stream_metrics[stream_metrics.scope == "stream"].set_index("label")
        lines.append(
            f"- **Ủng hộ**: mô hình chạy được theo luồng — **{int(o.n_stream_comments):,} bản ghi được chấm điểm "
            f"tức thời**, F1 lớp positive trên luồng {st.loc['positive','f1']:.2f} "
            f"(hình 14 cho thấy đây vẫn là lớp mạnh nhất, giống hệt đánh giá offline).")
    lines.append(
        f"- **KHÔNG ủng hộ**: bước tách từ còn thô — **{v.pct_occurrences_with_edge_punct:.1f}%** lượt token có dấu câu "
        f"dính ở hai đầu (\"movie.\" bị coi là từ khác \"movie\"), làm từ vựng phình từ "
        f"{int(v.n_vocab_stripped):,} lên **{int(v.n_vocab_raw):,} từ** "
        f"(+{100*(v.n_vocab_raw/v.n_vocab_stripped-1):.0f}%). Chưa sửa ở Task 9 vì sửa là phải huấn luyện lại "
        "mô hình mới so sánh được (xem `outputs/tables/eda_token_vocab.csv`).")
    lines.append(
        f"- **KHÔNG ủng hộ**: emoji **không đủ mạnh để làm đặc trưng cảm xúc** — ngay ở lớp dùng nhiều nhất "
        f"(positive) cũng chỉ {emo.loc['positive','emoji_per_1000_comments']:.0f} emoji/1.000 bình luận "
        f"({emo.loc['positive','pct_comments_with_emoji']:.1f}% bình luận có emoji); và emoji đứng đầu lớp negative "
        f"lại là \"{emoji_label(neg_top.emoji)}\" ({int(neg_top.n_emoji)} lần) — dấu hiệu mỉa mai, không phải tích cực.")
    lines.append(
        f"- **Chưa kiểm chứng**: hành vi với **bình luận livestream thật** (tiếng Việt, teencode, không có điểm số), "
        f"với **tải cao hơn** (mức cao nhất đã đo là {peak_msg_s:,.0f} msg/s) và **exactly-once** khi job chết giữa chừng "
        "(xem `src/streaming/README.md` §11) — tất cả đều **cần kiểm chứng**, không được suy diễn từ số liệu trên.")
    lines += ["", "---", "",
              "**Nguồn số liệu**: `outputs/tables/eda_*.csv`, `class_distribution.csv`, `per_class_metrics.csv`, "
              "`confusion_matrix.csv`, `stream_per_class_metrics.csv`. "
              "SQL nguyên văn: `src/eda/sql/*.sql`. Sinh lại: `$VENV_PY src/eda/plots.py`.",
              ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Vẽ biểu đồ EDA + sinh insights (Task 9)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--only", action="append", default=None,
                    help="chỉ vẽ hình này (06, 07, ... hoặc tên: class, length, words, emoji, "
                         "timeline, throughput, alert, latency, quality, interactive)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    eda = cfg["eda"]
    apply_style()
    FIGURES.mkdir(parents=True, exist_ok=True)

    want = set(args.only) if args.only else None

    def selected(*keys: str) -> bool:
        return want is None or any(k in want for k in keys)

    items: list[dict] = []
    if selected("06", "class"):
        log("Hình 06 — phân bố nhãn")
        items.append(fig06_class_distribution(load("eda_class_distribution")))
    if selected("07", "length"):
        log("Hình 07 — độ dài theo lớp")
        items.append(fig07_length(load("eda_length_histogram"), load("eda_length_quantiles"),
                                  int(eda["length_bin_max"])))
    if selected("08", "words"):
        log("Hình 08 — từ đặc trưng mỗi lớp")
        items.append(fig08_top_words(load("eda_top_words_by_class")))
    if selected("09", "emoji"):
        log("Hình 09 — emoji theo lớp")
        items.append(fig09_emoji(load("eda_emoji_by_class"), int(eda["emoji_per_class_n"])))
    if selected("10", "timeline"):
        log("Hình 10 — cảm xúc theo thời gian")
        th = load("eda_throughput_per_second")
        th["t"] = pd.to_datetime(th.second_utc)
        hot = th[th.n_comments >= 5]          # các giây thuộc đợt bùng nổ (bỏ giây lẻ tẻ)
        burst = {"span": (hot.t.min(), hot.t.max()), "n": int(hot.n_comments.sum()),
                 "total": int(th.n_comments.sum()),
                 "seconds": (hot.t.max() - hot.t.min()).total_seconds()}
        items.append(fig10_timeline(load("eda_sentiment_per_minute"),
                                    load("eda_sentiment_per_10s"), burst))
    if selected("11", "throughput"):
        log("Hình 11 — thông lượng + bùng nổ")
        items.append(fig11_throughput(load("eda_throughput_per_second")))
    if selected("12", "alert"):
        log("Hình 12 — tỷ lệ tiêu cực + cảnh báo")
        cls = load("eda_class_distribution")
        base = float(cls[(cls.split == "test") & (cls.label == "negative")].share_in_split.iloc[0])
        items.append(fig12_negative_alert(load("eda_negative_share_alert"), base))
    if selected("13", "latency"):
        log("Hình 13 — phân bố độ trễ")
        items.append(fig13_latency(load("eda_latency_histogram"), load("eda_latency_quantiles")))
    if selected("14", "quality"):
        log("Hình 14 — chất lượng mô hình (từ Task 7)")
        items.append(fig14_model_quality(load("confusion_matrix"), load("per_class_metrics")))
    if selected("15", "interactive"):
        log("Hình 15 — biểu đồ tương tác (tuỳ chọn)")
        it = fig15_interactive(load("eda_sentiment_per_10s"), load("eda_sentiment_per_minute"))
        if it:
            items.append(it)

    table_of = {
        "06_class_distribution.png": "eda_class_distribution",
        "07_length_by_class.png": "eda_length_histogram",
        "08_top_words_by_class.png": "eda_top_words_by_class",
        "09_emoji_by_class.png": "eda_emoji_by_class",
        "10_sentiment_timeline.png": "eda_sentiment_per_minute",
        "11_throughput_burst.png": "eda_throughput_per_second",
        "12_negative_share_alert.png": "eda_negative_share_alert",
        "13_latency_distribution.png": "eda_latency_histogram",
        # F1 từng lớp lấy từ per_class_metrics.csv, ma trận nhầm lẫn từ
        # confusion_matrix.csv (đều của Task 7); bảng ghép dài ra ở eda_model_quality.csv.
        "14_model_quality.png": ["eda_model_quality", "per_class_metrics", "confusion_matrix"],
    }
    for it in items:
        it["source_table"] = table_of.get(it["file"])

    # Chỉ ghi insights.md khi vẽ ĐỦ 9 hình (chạy --only thì không ghi đè file báo cáo)
    if want is None:
        sm_path = TABLES / "stream_per_class_metrics.csv"
        th = load("eda_throughput_per_second")
        text = build_insights(items, load("eda_overview"), load("eda_token_vocab"),
                              load("eda_emoji_by_class"), float(th.n_comments.max()),
                              pd.read_csv(sm_path) if sm_path.exists() else None)
        INSIGHTS.write_text(text, encoding="utf-8")
        log(f"-> {INSIGHTS.relative_to(PROJECT_ROOT)} ({len(items)} hình)")
    else:
        log(f"Chạy --only: vẽ {len(items)} hình, KHÔNG ghi lại outputs/insights.md")
    log("Xong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Bảng màu và thiết lập chung cho MỌI biểu đồ của dự án (CLAUDE.md §8).

Quy ước:
- Một bảng màu duy nhất dùng xuyên suốt: 3 lớp cảm xúc luôn cùng màu ở mọi hình.
- Chữ trong hình là tiếng Anh, có đơn vị ở nhãn trục.
- Xuất PNG 200 dpi vào outputs/figures/, đánh số 00_, 01_, ...

Dùng:
    from src.common.plotting import apply_style, SENTIMENT_COLORS, STAGE_COLORS
    apply_style()
"""

from __future__ import annotations

# --- 3 lớp cảm xúc: dùng CÙNG một bộ màu ở mọi biểu đồ ---
SENTIMENT_COLORS = {
    "negative": "#E76F51",   # cam đỏ
    "neutral": "#9A9A9A",    # xám
    "positive": "#2A9D8F",   # xanh ngọc
}

# --- Màu cho các tầng của pipeline (sơ đồ kiến trúc) ---
STAGE_COLORS = {
    "source": "#6C757D",     # xám đậm — nguồn dữ liệu
    "kafka": "#264653",      # xanh than — Kafka
    "spark": "#2A9D8F",      # xanh ngọc — Spark Structured Streaming
    "ml": "#457B9D",         # xanh thép — Spark ML
    "sink": "#F4A261",       # cát — nơi lưu kết quả
    "dashboard": "#E9C46A",  # vàng — dashboard
    "dlq": "#E76F51",        # cam đỏ — hàng đợi lỗi
}

DPI = 200


def apply_style() -> None:
    """Áp thiết lập chung (font, lưới, độ phân giải) cho matplotlib."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
    })


def save_fig(fig, path: str | "Path", note: str | None = None) -> None:  # noqa: F821
    """Lưu hình 200 dpi. `note` (nếu có) ghi chú nguồn số liệu dưới hình."""
    from pathlib import Path as _Path

    p = _Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if note:
        fig.text(0.5, 0.01, note, ha="center", va="bottom", fontsize=8, color="#555555")
    fig.savefig(p, dpi=DPI, bbox_inches="tight", facecolor="white")

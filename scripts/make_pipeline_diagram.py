#!/usr/bin/env python3
"""make_pipeline_diagram.py — Vẽ sơ đồ kiến trúc pipeline (Task 5, yêu cầu 7).

    .venv/bin/python scripts/make_pipeline_diagram.py

Kết quả: outputs/figures/00_pipeline_architecture.png (200 dpi, chữ tiếng Anh).
Số liệu in trên hình lấy từ outputs/tables/ingestion_report.csv và
logs/task5_1000msg_*.log — không bịa.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.common.plotting import STAGE_COLORS, apply_style, save_fig  # noqa: E402

apply_style()
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

INK = "#2B2B2B"


def box(ax, x0, y0, x1, y1, title, lines, color, text_color="white",
        title_size=9.5, body_size=7.2, dashed=False, line_color=None,
        title_dy=2.3, body_dy=6.0, body_step=3.1):
    """Hộp bo góc có tiêu đề + các dòng mô tả."""
    ax.add_patch(mpatches.FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle="round,pad=0.6,rounding_size=1.2",
        linewidth=1.2, edgecolor=line_color or color,
        facecolor=color, linestyle="--" if dashed else "-", zorder=2))
    cx = (x0 + x1) / 2
    ax.text(cx, y1 - title_dy, title, ha="center", va="top", color=text_color,
            fontsize=title_size, fontweight="bold", zorder=3)
    for i, line in enumerate(lines):
        ax.text(cx, y1 - body_dy - i * body_step, line, ha="center", va="top",
                color=text_color, fontsize=body_size, zorder=3)


def arrow(ax, p0, p1, color="#4A4A4A", style="-|>", lw=1.7, dashed=False):
    ax.add_patch(mpatches.FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=15, linewidth=lw, color=color,
        linestyle="--" if dashed else "-", shrinkA=1, shrinkB=1, zorder=1))


def elbow(ax, pts, color="#4A4A4A", lw=1.7):
    """Đường gấp khúc có mũi tên ở đoạn cuối."""
    for i in range(len(pts) - 2):
        arrow(ax, pts[i], pts[i + 1], color=color, style="-", lw=lw)
    arrow(ax, pts[-2], pts[-1], color=color, lw=lw)


def main() -> None:
    fig, ax = plt.subplots(figsize=(13.5, 8.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 98.5, "SentimentGuard — Real-Time Comment Sentiment Pipeline (architecture)",
            ha="center", va="top", fontsize=13.5, fontweight="bold", color=INK)
    ax.text(50, 95.4, "Replay data (offline, labeled) → Kafka → Spark Structured Streaming "
                      "→ Spark ML → results/dashboard",
            ha="center", va="top", fontsize=9, color="#555555", style="italic")

    # ---------------- Hàng 1: nguồn → producer → Kafka ----------------
    box(ax, 2, 74, 24, 91, "1 · Data source (offline)",
        ["IMDb Review Dataset (CC0)", "1,010,296 reviews · data/raw/part-01.json"],
        STAGE_COLORS["source"])

    box(ax, 28, 74, 50, 91, "2 · Replay producer",
        ["src/producer/replay_producer.py", "JSON message: comment_id, stream_id,",
         "user_hash (salted), text, event_ts  —  NO labels"],
        STAGE_COLORS["source"])

    # Kafka panel + 3 topic chips
    box(ax, 56, 70.5, 98, 92, "3 · Apache Kafka 4.3.1 (KRaft, no ZooKeeper)",
        [], STAGE_COLORS["kafka"], title_size=9.5)
    chips = [
        ("comments_raw", "3 partitions — raw comments"),
        ("comments_scored", "3 partitions — model output"),
        ("comments_dlq", "1 partition — bad records + reason"),
    ]
    for i, (name, desc) in enumerate(chips):
        y = 82.5 - i * 5.6
        ax.add_patch(mpatches.FancyBboxPatch(
            (58.5, y), 37, 4.4, boxstyle="round,pad=0.25,rounding_size=0.8",
            facecolor="#3C6470", edgecolor="none", zorder=3))
        ax.text(60, y + 2.2, name, ha="left", va="center", color="white",
                fontsize=8, fontweight="bold", family="DejaVu Sans Mono", zorder=4)
        ax.text(93.5, y + 2.2, desc, ha="right", va="center", color="#CFE3E6",
                fontsize=6.8, zorder=4)

    arrow(ax, (24, 82.5), (28, 82.5))
    arrow(ax, (50, 82.5), (56, 82.5))

    # ---------------- Hàng 2: Spark streaming → Spark ML ----------------
    box(ax, 2, 42, 44, 62, "4 · Spark Structured Streaming",
        ["src/streaming/ (Task 8)",
         "explicit schema via from_json · event time + watermark",
         "cleaning with Spark SQL functions — the same",
         "code path used for training (CLAUDE.md §4)",
         "bad / missing records → DLQ, never silently dropped"],
        STAGE_COLORS["spark"], body_size=7.0)

    box(ax, 48, 42, 98, 62, "5 · Spark ML Pipeline",
        ["src/training/ (Task 7)",
         "text cleaning → TF-IDF → classifier, all inside one Pipeline",
         "so TF-IDF is fitted on the TRAIN split only",
         "labels are never read here — they live in",
         "data/processed/eval_labels.parquet (evaluation only)"],
        STAGE_COLORS["ml"], body_size=7.0)

    elbow(ax, [(77, 70.5), (77, 64), (23, 64), (23, 62)])
    arrow(ax, (44, 52), (48, 52))

    # ---------------- Hàng 3: lưu kết quả → dashboard ----------------
    box(ax, 2, 16, 30, 33, "6 · Dead-letter queue",
        ["topic: comments_dlq", "invalid JSON / missing fields",
         "+ reason for rejection"],
        STAGE_COLORS["dlq"])
    arrow(ax, (16, 42), (16, 33), color=STAGE_COLORS["dlq"], dashed=True)

    box(ax, 34, 16, 62, 33, "7 · Result storage",
        ["Parquet: data/processed/ (scored comments)",
         "+ topic: comments_scored"],
        STAGE_COLORS["sink"], text_color=INK)
    elbow(ax, [(73, 42), (73, 37.5), (48, 37.5), (48, 33)])
    arrow(ax, (62, 24.5), (66, 24.5))

    box(ax, 66, 16, 98, 33, "8 · Streamlit dashboard",
        ["src/app/ (Task 10) — 3 tabs:",
         "Live Monitor · Try It · About",
         "aggregate-only display (no personal data)"],
        STAGE_COLORS["dashboard"], text_color=INK)

    # ---------------- Nhãn đánh giá (ngoài luồng) ----------------
    box(ax, 45, 65.5, 74, 70.4, "Labels stay OUT of the stream",
        ["eval_labels.parquet → offline macro-F1 only"],
        "#FFFFFF", text_color="#555555", title_size=7.4, body_size=6.8,
        dashed=True, line_color="#9A9A9A", title_dy=1.6, body_dy=3.4, body_step=2.6)
    arrow(ax, (48, 74), (48, 70.6), color="#9A9A9A", lw=1.2, dashed=True)

    # ---------------- Chú thích số liệu đo được ----------------
    ax.text(2, 9.5,
            "Measured on this VM (2026-10-14, Kafka single broker + JDK 17): replay producer "
            "3,229–3,615 msg/s unlimited (never below the configured rate: 100→100.0, "
            "500→499.0 msg/s);\nend-to-end check: 1,000 messages sent, 1,000 read back, 0 errors "
            "(logs/task5_1000msg_*.log). Numbers from outputs/tables/ingestion_report.csv.",
            ha="left", va="top", fontsize=7.4, color="#555555")
    ax.text(2, 3.5,
            "Diagram is illustrative of the architecture; solid arrows = online data flow, "
            "dashed red = error path, dashed grey = offline/evaluation artifacts.",
            ha="left", va="top", fontsize=7.0, color="#777777", style="italic")

    out = PROJECT_ROOT / "outputs/figures/00_pipeline_architecture.png"
    save_fig(fig, out)
    print("Đã lưu:", out.relative_to(PROJECT_ROOT))
    plt.close(fig)


if __name__ == "__main__":
    main()

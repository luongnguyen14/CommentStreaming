"""Test nhỏ cho dashboard (Task 10) — các hàm THUẦN trong `src/app/app.py`.

Chạy:
    source scripts/env.sh
    .venv/bin/python -m pytest tests/ -q

Vì sao test riêng phần này: đây là chỗ dễ sai âm thầm nhất của dashboard —
(a) gộp cửa sổ của nhiều phòng mà quên nhân trọng số cho độ trễ,
(b) xét cảnh báo theo **giờ hệ thống** thay vì thời gian dữ liệu (với dữ liệu
replay thì "bây giờ" không tồn tại, và cửa sổ 1 bình luận luôn cho 100%),
(c) che từ nhạy cảm bằng `in` nên che cả "stupidity" khi chỉ định che "stupid".
Ba lỗi đó đều không làm app crash, chỉ làm số hiển thị sai.

Không cần Spark: mọi hàm dưới đây chỉ dùng pandas. (`src/app/app.py` vẫn import
được vì `get_spark_model` chỉ nạp PySpark khi thực sự gọi.)
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.app.app import (  # noqa: E402
    LABELS, aggregate_windows, eval_alerts, fmt_utc, list_runs, mask_text,
    minute_from_detail, read_table, windows_from_detail, chart_current,
    chart_probability, chart_timeline, chart_volume)
from src.common.utils import load_config  # noqa: E402

VERIFY1 = PROJECT_ROOT / "outputs" / "stream" / "verify1"
SLIDE = VERIFY1 / "window_sliding_10s"
needs_verify1 = pytest.mark.skipif(
    not SLIDE.exists(), reason="chưa có outputs/stream/verify1 (Task 8 chưa chạy)")

T0 = datetime(2026, 10, 15, 18, 0, 0)


# ---------------------------------------------------------------------------
# Đọc dữ liệu
# ---------------------------------------------------------------------------
def test_read_table_missing_dir_khong_phai_loi(tmp_path):
    """Thư mục chưa tồn tại = job chưa chạy, KHÔNG phải lỗi -> (rỗng, None)."""
    df, err = read_table(tmp_path / "khong-ton-tai", "window_1min")
    assert df.empty and err is None


def test_read_table_dir_rong(tmp_path):
    (tmp_path / "window_1min").mkdir()
    df, err = read_table(tmp_path, "window_1min")
    assert df.empty and err is None


def test_read_table_bat_loi_that(tmp_path):
    """File rác trong thư mục -> phải trả thông báo lỗi, không ném ra ngoài."""
    d = tmp_path / "window_1min"
    d.mkdir()
    (d / "part-00000.parquet").write_bytes(b"day khong phai parquet")
    df, err = read_table(tmp_path, "window_1min", tries=1)
    assert df.empty and err and "Error" in err or "error" in (err or "").lower()


def test_list_runs(tmp_path):
    assert list_runs(tmp_path / "khong-co") == []
    (tmp_path / "run_a" / "window_1min").mkdir(parents=True)
    (tmp_path / "run_b").mkdir()                       # không có bảng nào -> bỏ qua
    assert list_runs(tmp_path) == ["run_a"]


# ---------------------------------------------------------------------------
# Gộp cửa sổ + dựng cửa sổ từ bảng chi tiết
# ---------------------------------------------------------------------------
def _fake_windows():
    """4 phòng, 2 cửa sổ — cố tình lệch kích thước để bắt lỗi trung bình cộng."""
    rows = []
    for sid, n_n, n_neu, n_pos, lat in [
        ("room-a", 3, 1, 6, 100.0),      # 10 bình luận, độ trễ 100 ms
        ("room-b", 0, 0, 1, 500.0),      # 1 bình luận, độ trễ 500 ms
        ("room-c", 1, 1, 1, 200.0),
    ]:
        rows.append(dict(window_start=T0, window_end=T0 + timedelta(minutes=1),
                         stream_id=sid, n_comments=n_n + n_neu + n_pos,
                         n_negative=n_n, n_neutral=n_neu, n_positive=n_pos,
                         avg_latency_ms=lat))
    rows.append(dict(window_start=T0 + timedelta(minutes=1),
                     window_end=T0 + timedelta(minutes=2), stream_id="room-a",
                     n_comments=2, n_negative=0, n_neutral=0, n_positive=2,
                     avg_latency_ms=50.0))
    return pd.DataFrame(rows)


def test_aggregate_windows_cong_don_va_trong_so():
    agg = aggregate_windows(_fake_windows())
    assert len(agg) == 2 and list(agg.n_comments) == [14, 2]   # 10 + 1 + 3, rồi 2
    assert list(agg.n_negative) == [4, 0]
    # trung bình CÓ TRỌNG SỐ theo số bình luận của từng phòng:
    assert agg.avg_latency_ms.iloc[0] == pytest.approx((10 * 100 + 1 * 500 + 3 * 200) / 14)
    assert agg.avg_latency_ms.iloc[1] == pytest.approx(50.0)
    assert agg.share_negative.iloc[0] == pytest.approx(4 / 14)
    assert agg.share_neutral.iloc[1] == 0.0                    # cửa sổ không có neutral
    assert agg.window_start.is_monotonic_increasing            # đã sắp xếp theo thời gian


def test_aggregate_windows_rong():
    assert aggregate_windows(pd.DataFrame()).empty
    assert aggregate_windows(None).empty


def _fake_detail(n=5):
    return pd.DataFrame({
        "comment_id": [f"c{i}" for i in range(n)],
        "stream_id": ["room-a"] * n,
        "event_time": pd.to_datetime([T0 + timedelta(seconds=s)
                                      for s in (0, 20, 61, 90, 119)]),
        "pred_label": ["negative", "positive", "neutral", "positive", "positive"],
        "confidence": [0.9] * n,
        "latency_ms": [1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
        "text_len": [10] * n,
    })


def test_windows_from_detail_theo_phut():
    minute = windows_from_detail(_fake_detail(), 60)
    assert list(minute.n_comments) == [2, 3]                   # 0–60 s, 60–120 s
    assert list(minute.window_start) == [pd.Timestamp(T0), pd.Timestamp(T0 + timedelta(minutes=1))]
    assert minute.n_negative.tolist() == [1, 0]
    assert minute.avg_latency_ms.iloc[0] == pytest.approx(1500.0)   # (1000+2000)/2
    assert minute.avg_latency_ms.iloc[1] == pytest.approx(4000.0)   # (3000+4000+5000)/3
    # cửa sổ 10 giây: 5 mốc giây 0,20,61,90,119 -> 5 ô khác nhau (0,20,60,90,110)
    assert len(windows_from_detail(_fake_detail(), 10)) == 5
    assert minute_from_detail(_fake_detail()).n_comments.sum() == 5


def test_windows_from_detail_rong():
    assert windows_from_detail(pd.DataFrame(), 60).empty
    assert windows_from_detail(None, 60).empty


# ---------------------------------------------------------------------------
# Cảnh báo — quy tắc đã đo ở Task 9 (config: eda.alert)
# ---------------------------------------------------------------------------
def _agg(rows):
    df = pd.DataFrame([dict(window_start=T0 + timedelta(seconds=10 * i),
                            window_end=T0 + timedelta(seconds=10 * i + 10),
                            **r) for i, r in enumerate(rows)])
    df["n_comments"] = df.n_negative + df.n_neutral + df.n_positive
    for l in LABELS:
        df[f"share_{l}"] = df[f"n_{l}"] / df.n_comments
    return df


def test_alert_khong_bao_khi_duoi_nguong():
    st_ = eval_alerts(_agg([dict(n_negative=2, n_neutral=4, n_positive=4)]), 0.30, 5, 30)
    assert st_["has_data"] and not st_["alert"]
    assert st_["share_negative"] == pytest.approx(0.2) and st_["n_comments"] == 10


def test_alert_bao_khi_vuot_nguong():
    st_ = eval_alerts(_agg([dict(n_negative=7, n_neutral=3, n_positive=3)]), 0.30, 5, 30)
    assert st_["alert"] and st_["hit"].share_negative == pytest.approx(7 / 13)


def test_alert_bo_qua_cua_so_qua_it_binh_luan():
    """1 bình luận tiêu cực = 100% -> KHÔNG được báo động (đo ở Task 9: 13 báo giả)."""
    st_ = eval_alerts(_agg([dict(n_negative=1, n_neutral=0, n_positive=0)]), 0.30, 5, 30)
    assert st_["has_data"] and not st_["alert"]


def test_alert_chi_xet_du_lieu_gan_nhat_chu_khong_theo_gio_he_thong():
    """Cửa sổ cũ vượt ngưỡng nhưng nằm ngoài `recent_s` -> không cảnh báo.

    Đây là điều kiện bắt buộc với dữ liệu REPLAY: mốc so sánh là `window_end` lớn
    nhất TRONG DỮ LIỆU (năm 2026 vẫn tính là 'gần đây'), không phải giờ hệ thống.
    """
    rows = [dict(n_negative=9, n_neutral=1, n_positive=0)] + \
           [dict(n_negative=0, n_neutral=5, n_positive=5) for _ in range(5)]
    st_ = eval_alerts(_agg(rows), 0.30, 5, 30)
    assert st_["has_data"] and not st_["alert"]      # 30 giây cuối chỉ có cửa sổ lành
    assert st_["n_recent"] == 3
    # mở rộng cửa sổ "hiện tại" ra 60 giây -> cửa sổ tiêu cực lọt vào -> phải báo
    assert eval_alerts(_agg(rows), 0.30, 5, 60)["alert"]


def test_alert_khong_co_du_lieu():
    st_ = eval_alerts(pd.DataFrame(), 0.30, 5, 30)
    assert not st_["has_data"] and not st_["alert"] and st_["share_negative"] is None


@needs_verify1
def test_alert_tren_du_lieu_that_verify1():
    """Khớp số đã đo ở Task 9 (outputs/insights.md hình 12) + giới hạn của quy tắc.

    Đo lại trên `outputs/stream/verify1` (15/10/2026):
      - đúng **1** cửa sổ vượt 30% tiêu cực với ≥5 bình luận: 18:08:30 UTC,
        38,46% (5/13);
      - 30 giây CUỐI của lần chạy toàn cửa sổ 1 bình luận, đều 100% tiêu cực →
        nếu không có điều kiện ≥5 bình luận thì dashboard báo động giả ngay khi
        xem lại dữ liệu này (đúng điều Task 9 đã cảnh báo: 13 báo động giả).
    Đổi kết quả test này = đổi quy tắc hoặc đổi dữ liệu → phải ghi vào PROGRESS.md.
    """
    cfg = load_config()
    thr = float(cfg["eda"]["alert"]["negative_share_threshold"])
    min_n = int(cfg["eda"]["alert"]["min_comments"])
    slide, err = read_table(VERIFY1, "window_sliding_10s")
    assert err is None and not slide.empty
    agg = aggregate_windows(slide)

    hits = agg[(agg.share_negative > thr) & (agg.n_comments >= min_n)]
    assert len(hits) == 1, "Task 9 đo được ĐÚNG 1 cửa sổ vượt ngưỡng trong verify1"
    hit = hits.iloc[0]
    assert hit.share_negative == pytest.approx(0.3846, abs=1e-3)
    assert int(hit.n_comments) == 13

    st_ = eval_alerts(agg, thr, min_n, 30)                 # trạng thái "hiện tại"
    assert st_["has_data"] and st_["share_negative"] == pytest.approx(1.0)
    assert st_["n_comments"] == 3
    assert not st_["alert"], "3 bình luận < ngưỡng 5 -> KHÔNG được cảnh báo"
    # hạ ngưỡng số bình luận xuống 1 -> quy tắc (dở) này báo động: chứng minh
    # điều kiện min_comments mới là thứ chặn báo động giả, không phải ngưỡng tỷ lệ
    assert eval_alerts(agg, thr, 1, 30)["alert"]


# ---------------------------------------------------------------------------
# Che dữ liệu nhạy cảm (CLAUDE.md §7)
# ---------------------------------------------------------------------------
def test_mask_text_tu_nhay_cam():
    mw, mp = ["stupid", "idiot"], []
    assert mask_text("You STUPID idiot", mw, mp) == "You *** ***"
    # ranh giới từ: KHÔNG che khi từ nằm trong từ khác
    assert mask_text("stupidity is not stupid", mw, mp) == "stupidity is not ***"
    assert mask_text("the idiot's hat", mw, mp) == "the ***'s hat"     # ' là ranh giới


def test_mask_text_email_va_dien_thoai():
    mp = [r"[\w.+-]+@[\w-]+\.[\w.]+", r"\b(?:\+?\d[\d .-]{7,}\d)\b"]
    out = mask_text("mail me at an.nguyen+spam@example.com.vn or call 0912345678 ok",
                    [], mp)
    assert "an.nguyen" not in out and "[đã che]" in out
    assert "0912345678" not in out
    assert out.count("[đã che]") == 2


def test_mask_text_rong_va_khong_co_tu_khoa():
    assert mask_text("", ["stupid"], []) == ""
    assert mask_text(None, ["stupid"], []) == ""
    assert mask_text("bình luận bình thường", ["stupid"], []) == "bình luận bình thường"


def test_mask_dung_duoc_danh_sach_that_trong_config():
    cfg = load_config()
    d = cfg["dashboard"]
    out = mask_text("This garbage is stupid, mail x@y.com", d["mask_words"], d["mask_patterns"])
    assert "garbage" not in out and "stupid" not in out and "x@y.com" not in out


# ---------------------------------------------------------------------------
# Định dạng + biểu đồ (smoke test: dựng được figure từ dữ liệu thật/rỗng)
# ---------------------------------------------------------------------------
def test_fmt_utc():
    assert fmt_utc(T0) == "18:00:00"
    assert fmt_utc(None) == "—" and fmt_utc(pd.NaT) == "—"


def test_cac_bieu_do_dung_duoc():
    agg = _agg([dict(n_negative=2, n_neutral=3, n_positive=5),
                dict(n_negative=1, n_neutral=1, n_positive=8)])
    cur = chart_current(agg)                       # lấy cửa sổ CUỐI: 10%, 10%, 80%
    assert len(cur.data) == 1 and len(cur.data[0].x) == 3
    assert list(cur.data[0].x) == pytest.approx([10.0, 10.0, 80.0])
    assert list(cur.data[0].marker.color) == ["#E76F51", "#9A9A9A", "#2A9D8F"]
    assert len(chart_timeline(agg, "cửa sổ 1 phút").data) == 3      # 1 trace / lớp
    assert len(chart_volume(agg).data) == 1
    assert len(chart_probability({"negative": 0.2, "neutral": 0.3, "positive": 0.5}).data) == 1
    # nhãn trục bằng TIẾNG ANH (CLAUDE.md §8) và có đơn vị
    assert "Share of comments (%)" in cur.layout.xaxis.title.text
    assert "Comments per minute" in chart_volume(agg).layout.yaxis.title.text


@needs_verify1
def test_doc_duoc_du_lieu_that_verify1():
    detail, err = read_table(VERIFY1, "scored_detail")
    assert err is None and not detail.empty
    assert "user_hash" in detail.columns            # có trong dữ liệu ...
    assert "text_clean" not in detail.columns       # ... nhưng KHÔNG lưu văn bản (mặc định)
    assert set(detail.pred_label.unique()) <= set(LABELS)
    assert len(list_runs(VERIFY1.parent)) >= 1

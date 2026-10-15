"""Test cho cách lấy mẫu theo phần trăm của `prepare.py` (Task 6).

Chạy:
    source scripts/env.sh
    .venv/bin/python -m pytest tests/ -q

Trọng tâm: cách chọn tập con phải **TẤT ĐỊNH** (chạy lại ra đúng tập cũ — cả dự án
dựa vào tính chất này: mọi con số trong báo cáo gắn với một tập dữ liệu xác định)
và phải **LỒNG NHAU** (20% ⊂ 64% ⊂ 100%), nếu không thì "thêm dữ liệu" hoá ra là
đổi sang một tập khác chứ không phải thêm vào.

`keep_record` là hàm thuần nên test ở đây không cần SparkSession.
"""

from __future__ import annotations

import sys
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.training.prepare import _PCT_SCALE, keep_record, subsample_pct_from_config  # noqa: E402

# Id giả có dạng giống id thật của nguồn ("rw…"), cố định nên test tất định.
IDS = [f"rw{i:09d}" for i in range(20_000)]


def giu_lai(pct: int, ids: list[str] | None = None) -> list[str]:
    return [i for i in (ids or IDS) if keep_record(i, pct)]


def id_co_so_du(so_du: int) -> str:
    """Tìm một id có `crc32(id) % 1000` đúng bằng `so_du` — để kiểm đúng biên."""
    for i in range(200_000):
        rid = f"rw{i:09d}"
        if zlib.crc32(rid.encode("utf-8")) % _PCT_SCALE == so_du:
            return rid
    raise AssertionError(f"không tìm được id có số dư {so_du}")


# ------------------------------------------------------------------ độ phủ ---
def test_pct_100_giu_tat_ca():
    assert len(giu_lai(100)) == len(IDS)


def test_pct_64_giu_dung_khoang_64_phan_tram():
    """Sai số cho phép 1,5 điểm % — rộng hơn 4 lần độ lệch chuẩn ở n=20.000."""
    ty_le = len(giu_lai(64)) / len(IDS)
    assert abs(ty_le - 0.64) < 0.015, f"giữ {ty_le:.4f}, lệch quá xa 64%"


def test_cac_muc_phan_tram_deu_bam_sat_muc_tieu():
    """Vài mốc hay dùng phải ra đúng tỷ lệ — đây là con số ghi trong config.yaml."""
    for pct in (10, 20, 50, 64, 70):
        ty_le = len(giu_lai(pct)) / len(IDS)
        assert abs(ty_le - pct / 100) < 0.015, f"pct={pct} ra {ty_le:.4f}"


def test_pct_1_van_con_du_lieu():
    """Kẹp cận dưới: 1% vẫn phải có bản ghi, không được ra tập rỗng."""
    assert 0 < len(giu_lai(1)) < len(IDS) / 10


# --------------------------------------------------------------- tính chất ---
def test_tat_dinh_chay_lai_ra_dung_tap_cu():
    """Cùng đầu vào -> cùng kết quả. Mọi số liệu báo cáo phụ thuộc tính chất này."""
    assert giu_lai(64) == giu_lai(64)


def test_khong_phu_thuoc_thu_tu():
    """Đảo thứ tự đầu vào không đổi tập được chọn (không lệch theo thứ tự file)."""
    assert set(giu_lai(64)) == set(giu_lai(64, list(reversed(IDS))))


def test_cac_muc_long_nhau():
    """20% ⊂ 64% ⊂ 100% — 'thêm dữ liệu' phải là thêm vào, không phải đổi tập."""
    s20, s64, s100 = (set(giu_lai(p)) for p in (20, 64, 100))
    assert s20 < s64 < s100, "các mức phần trăm không lồng nhau"


def test_id_trung_nhau_thi_cung_so_phan():
    """Nguồn có 15.601 review_id lặp: bản ghi trùng id phải cùng được giữ hoặc cùng bị loại."""
    trung = ["rw000000042"] * 5
    assert len(giu_lai(64, trung)) in (0, 5)


def test_bien_dung_nguong():
    """`crc32 % 1000 == pct*10 - 1` được giữ, `== pct*10` bị loại — không lệch một đơn vị."""
    assert keep_record(id_co_so_du(639), 64)
    assert not keep_record(id_co_so_du(640), 64)


# ------------------------------------------------- tương thích ngược config ---
def test_config_kieu_moi():
    assert subsample_pct_from_config({"prepare": {"subsample_pct": 64}}) == 64


def test_config_kieu_cu_duoc_quy_doi():
    """Config còn `subsample_mod` (trước 15/10/2026) vẫn chạy, có cảnh báo."""
    assert subsample_pct_from_config({"prepare": {"subsample_mod": 5}}) == 20
    assert subsample_pct_from_config({"prepare": {"subsample_mod": 1}}) == 100


def test_config_thieu_ca_hai_thi_lay_het():
    assert subsample_pct_from_config({"prepare": {}}) == 100


def test_config_kep_gia_tri_ngoai_khoang():
    """pct ngoài [1, 100] bị kẹp lại, không làm hỏng phép lọc."""
    assert subsample_pct_from_config({"prepare": {"subsample_pct": 900}}) == 100
    assert subsample_pct_from_config({"prepare": {"subsample_pct": 0}}) == 1


# ------------------------------------------------------- ensure_jsonl thật ---
def test_manifest_cu_tu_dong_buoc_sinh_lai(tmp_path):
    """Manifest thiếu khóa `subsample_pct` (bản cũ) phải bị coi là KHÔNG khớp.

    Đây là cơ chế then chốt của lần đổi sang phần trăm: không phải xóa tay
    `_manifest.json`, chỉ cần đổi tham số là JSONL tự sinh lại.
    """
    import json

    from src.training.prepare import ensure_jsonl

    raw = tmp_path / "part-01.json"
    recs = [{"review_id": f"rw{i:05d}", "reviewer": "u", "movie": f"m{i % 3}",
             "rating": "8", "review_date": "2015-01-01", "review_detail": "x" * 30}
            for i in range(400)]
    raw.write_text("[\n" + ",\n".join(json.dumps(r) for r in recs) + "\n]\n", encoding="utf-8")
    d = tmp_path / "jsonl"

    # Lần 1: sinh mới, ghi khóa MỚI
    _, n100 = ensure_jsonl(raw, d, truncate=100, subsample_pct=100)
    m = json.loads((d / "_manifest.json").read_text(encoding="utf-8"))
    assert n100 == 400 and m["subsample_pct"] == 100
    assert "subsample_mod" not in m, "manifest còn khóa cũ"

    # Lần 2 y hệt: phải BỎ QUA (không đổi file)
    import os
    mtime = os.stat(d / "part-000.jsonl").st_mtime_ns
    _, n_lai = ensure_jsonl(raw, d, truncate=100, subsample_pct=100)
    assert n_lai == 400 and os.stat(d / "part-000.jsonl").st_mtime_ns == mtime

    # Lần 3: đổi pct -> phải SINH LẠI và ra tập nhỏ hơn
    _, n40 = ensure_jsonl(raw, d, truncate=100, subsample_pct=40)
    assert 130 <= n40 <= 190, f"pct=40 giữ {n40}/400, lệch quá xa"
    assert os.stat(d / "part-000.jsonl").st_mtime_ns != mtime
    # và tập 40% phải là TẬP CON của tập 100% (đọc lại chính các dòng đã ghi)
    kept = [json.loads(l)["review_id"] for l in
            (d / "part-000.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(keep_record(i, 40) for i in kept)


def test_manifest_cu_thieu_khoa_thi_sinh_lai(tmp_path):
    """Mô phỏng manifest của code TRƯỚC 15/10/2026 (chỉ có `subsample_mod`)."""
    import json

    from src.training.prepare import ensure_jsonl

    raw = tmp_path / "part-01.json"
    recs = [{"review_id": f"rw{i:05d}", "reviewer": "u", "movie": "m", "rating": "8",
             "review_date": "2015-01-01", "review_detail": "x" * 30} for i in range(200)]
    raw.write_text("[\n" + ",\n".join(json.dumps(r) for r in recs) + "\n]\n", encoding="utf-8")
    d = tmp_path / "jsonl"
    d.mkdir()
    (d / "_manifest.json").write_text(json.dumps({
        "source": raw.name, "source_size": raw.stat().st_size, "truncate": 100,
        "subsample_mod": 5, "n_records": 40, "n_seen": 200}), encoding="utf-8")
    (d / "part-000.jsonl").write_text("", encoding="utf-8")

    _, n = ensure_jsonl(raw, d, truncate=100, subsample_pct=100)
    assert n == 200, "manifest cũ vẫn được chấp nhận -> JSONL không được sinh lại"

"""Tiện ích dùng chung: đọc config, băm có muối, đọc file JSON lớn theo dòng.

Quy ước liên quan (CLAUDE.md):
- §7 Quyền riêng tư: mã người dùng phải băm **có muối**, muối đọc từ biến môi
  trường (`COMMENT_HASH_SALT`) — không bao giờ hard-code muối trong code.
- §3: tham số để trong `config.yaml`, không hard-code trong script.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SALT_ENV_VAR = "COMMENT_HASH_SALT"


class MissingSaltError(RuntimeError):
    """Thiếu biến môi trường chứa muối băm."""


def load_config(path: str | Path | None = None) -> dict:
    """Đọc config.yaml (mặc định ở gốc dự án)."""
    import yaml  # import muộn để hàm này không kéo phụ thuộc vào mọi script

    cfg_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_salt() -> bytes:
    """Đọc muối băm từ biến môi trường. Thiếu thì báo lỗi rõ ràng, không đoán."""
    salt = os.environ.get(SALT_ENV_VAR)
    if not salt:
        raise MissingSaltError(
            f"Thiếu biến môi trường {SALT_ENV_VAR}. Sinh muối (một lần) rồi thêm vào ~/.bashrc:\n"
            f'  python3 -c "import secrets; print(\'export {SALT_ENV_VAR}=\' + secrets.token_hex(16))"'
        )
    return salt.encode("utf-8")


def salted_hash(user_id: str, salt: bytes | None = None, length: int = 16) -> str:
    """Băm có muối mã người dùng (SHA-256, hex cắt ngắn).

    Cùng một người dùng + cùng muối -> cùng hash (để đếm được "một người bình
    luận nhiều lần"), nhưng không thể tra ngược ra mã gốc.
    """
    salt = salt if salt is not None else get_salt()
    digest = hashlib.sha256(salt + user_id.encode("utf-8")).hexdigest()
    return digest[:length]


def iter_json_array(path: str | Path, chunk_size: int = 1 << 20):
    """Sinh (yield) từng object trong một file JSON dạng mảng, không nạp cả file.

    `data/raw/part-01.json` nặng ~1,1 GB nên `json.load` sẽ hết RAM; hàm này chỉ
    giữ trong bộ nhớ một đoạn đệm nhỏ, đủ để giải mã từng bản ghi.
    """
    decoder = json.JSONDecoder()
    buf = ""
    pos = 0
    exhausted = False
    with open(path, encoding="utf-8") as f:
        while True:
            # Bỏ qua ký tự phân cách cấu trúc giữa các bản ghi: khoảng trắng, ',', '['.
            while pos < len(buf) and buf[pos] in " \t\r\n,[":
                pos += 1
            if pos < len(buf) and buf[pos] == "]":   # hết mảng
                return
            if pos >= len(buf) and exhausted:
                return
            try:
                obj, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                if exhausted:
                    raise
                more = f.read(chunk_size)            # bản ghi bị cắt ngang -> đọc thêm
                if not more:
                    exhausted = True
                    continue
                if pos:
                    buf = buf[pos:]
                    pos = 0
                buf += more
                continue
            pos = end
            yield obj
            if pos > chunk_size:
                buf = buf[pos:]
                pos = 0

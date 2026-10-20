#!/usr/bin/env bash
# run_comment_stream.sh — Chạy từng comment: comment đến -> phân tích -> kết quả.
#
#   bash scripts/run_comment_stream.sh                  # 12 comment, nghỉ 1s/comment
#   bash scripts/run_comment_stream.sh --limit 20       # 20 comment
#   bash scripts/run_comment_stream.sh --fast           # không nghỉ
#   bash scripts/run_comment_stream.sh --no-bad         # bỏ 4 bản ghi lỗi cố ý
#
# Đây là chế độ --one-by-one của terminal_app.py; dùng đúng parse_stream,
# clean_text và PipelineModel của hệ thống.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$HERE/run_terminal_app.sh" --one-by-one "$@"

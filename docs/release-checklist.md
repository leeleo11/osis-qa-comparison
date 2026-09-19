# Release checklist

1. `git status --short` 中没有数据或结果文件。
2. `uv run pytest -q` 全部通过。
3. `uv run python scripts/audit_public_boundary.py` 返回 `ok: true`。
4. 对目标父仓库运行 `scripts/verify_parent_protocol.py`。
5. dry-run 只显示 task_id/category，不显示题面、gold、alias 或 source。
6. `git ls-files` 不含 datasets、questions、runs、results、private、tmp、凭据或本机路径。
7. 远端 commit 与本地 `main` 完全一致。

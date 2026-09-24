# Reproducibility

## 1. 固定两个仓库版本

克隆本实验仓库与父仓库：

```powershell
git clone https://github.com/leeleo11/osis-qa-comparison.git
git clone https://github.com/osis-ai/osis-skill-enhance.git
```

每个 run 的 `manifest.json` 都记录 `parent_commit`、知识快照 SHA256、模型、variant、seed 和预算。复现实验时应将父仓库检出到 manifest 中的提交；当前建仓协议基线为 `650b37f4689dcc34ccebb0ede9e978b51c79447a`。

## 2. 安装 Python 3.13 与框架环境

```powershell
uv sync --python 3.13 --extra test
uv run python scripts/setup_framework_envs.py
```

脚本建立相互隔离的 `.venvs/main`、`.venvs/t2`、`.venvs/t3`、`.venvs/t4`、`.venvs/t5`。T1 与 T6 使用 main 环境；T2–T5 使用各自框架环境，避免依赖冲突。

## 3. 配置父仓库

任选一种：

1. 每次命令传 `--parent-repo`；
2. 设置 `OSIS_PARENT_REPO`；
3. 将 `configs/parent_repo.example.txt` 复制为被忽略的 `configs/parent_repo.local.txt`，填绝对路径。

父仓库必须包含 `.agents/skills`、`datasets/qa/questions.json` 和 `datasets/qa/system_prompt.txt`。

## 4. 创建本地知识快照

```powershell
uv run python scripts/create_knowledge_snapshot.py `
  --parent-repo C:\path\to\osis-skill-enhance `
  --output tmp\qa-knowledge-snapshot
```

脚本完整复制父仓库 `.agents/skills`，与 T6 所在 OpenCode 能读到的技能树一致。`datasets/qa` 里的 questions、gold、aliases 与 source 不会进入快照。`tmp/` 被 Git 忽略。

校验本地评分器与父仓库协议：

```powershell
uv run python scripts/verify_parent_protocol.py --parent-repo C:\path\to\osis-skill-enhance
```

## 5. 配置模型与 T6

在当前 shell 或秘密管理器中设置：

```powershell
$env:OSIS_MODEL_API_KEY = '<local-secret>'
$env:OSIS_MODEL_BASE_URL = 'http://your-gateway/v1'
```

T1–T5 使用上面的模型网关。T2–T5 调用 `list_knowledge_bases` 和 `hybrid_search`。不设置 `WEKNORA_API_KEY` 时，使用父仓库 OpenCode 的检索密钥。T1 没有工具循环，不查库。T6 不在本仓库启动 OpenCode，也不修改 bash、edit 或外部目录权限。先按父仓库 `datasets/qa/run_eval.py --via agent` 的方式启动 OpenCode（默认 `http://127.0.0.1:4096`），本仓库再调用同一个 `chat_via_agent`。题面只含系统提示和 Question。

## 6. 先 dry-run，再运行

```powershell
uv run python scripts/run_dataset.py `
  --parent-repo C:\path\to\osis-skill-enhance `
  --architecture T4 `
  --skills-dir tmp\qa-knowledge-snapshot `
  --dry-run
```

完整六框架矩阵：

```powershell
uv run python scripts/run_campaign.py `
  --parent-repo C:\path\to\osis-skill-enhance `
  --architectures T1 T2 T3 T4 T5 T6 `
  --skills-dir tmp\qa-knowledge-snapshot `
  --model deepseek-v4.1-flash-expires-on-0910 `
  --base-url $env:OSIS_MODEL_BASE_URL `
  --seed 0 `
  --label formal-qa-v1 `
  --jobs 1
```

`--jobs` 只影响 T1–T5。T6 始终串行，因为它复用父仓库正在运行的 OpenCode。正式对比建议 `--jobs 1`，减少网关负载差异。

同一个 label、架构、题号和 seed 再次运行时，旧目录先移入 `runs/_archive/<UTC时间>/`；汇总器忽略归档，只统计当前 attempt。`--resume` 会直接复用已经完成的当前 attempt。

## 7. 汇总本地结果

```powershell
uv run python scripts/summarize_results.py `
  --runs-dir runs\formal-qa-v1 `
  --output results\formal-qa-v1
```

输出为 `summary.json` 与 `records.csv`。数据、回复和结果均不上传；需要共享结论时，应另行生成去标识化统计表。
失败 attempt 会以错误答案进入统计，并在 `errors`、`failed_ids` 和 CSV 状态列中保留审计信息。

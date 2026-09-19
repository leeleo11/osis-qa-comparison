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

脚本只复制父协议列出的三类 gold source：`SKILL.md`、`pyosis_doc.py`、`项目画像.md`。模板代码、questions、gold、aliases 与 source 字段不会进入快照。`tmp/` 被 Git 忽略。

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

T6 需要 `opencode` 可执行文件。若不在 PATH，设置 `OPENCODE_EXE` 或传 `--opencode-executable`。默认复制固定父仓库的 `.agents/AGENTS.md` 作为 OSIS-AI 原生指令，并另加一份实验边界指令；也可用 `--osis-agents-file` 显式指定随 OSIS 安装的原生文件。T6 为每题创建独立 config、XDG config/data/cache/state 和会话，禁止 Shell、编辑与外部目录访问，并从子进程环境移除父仓库位置和无关 API key。

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

`--jobs` 只影响 T1–T5；T6 始终进入独立串行 lane。正式对比建议 `--jobs 1`，减少网关负载差异。

同一个 label、架构、题号和 seed 再次运行时，旧目录先移入 `runs/_archive/<UTC时间>/`；汇总器忽略归档，只统计当前 attempt。`--resume` 会直接复用已经完成的当前 attempt。

## 7. 汇总本地结果

```powershell
uv run python scripts/summarize_results.py `
  --runs-dir runs\formal-qa-v1 `
  --output results\formal-qa-v1
```

输出为 `summary.json` 与 `records.csv`。数据、回复和结果均不上传；需要共享结论时，应另行生成去标识化统计表。
失败 attempt 会以错误答案进入统计，并在 `errors`、`failed_ids` 和 CSV 状态列中保留审计信息。

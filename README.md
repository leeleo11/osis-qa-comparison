# OSIS QA Six-Framework Comparison

本仓库是 OSIS 第三条实验任务线：在同一批 API 问答上比较 T1–T6 六种智能体架构。父仓库协议采用 GAIA 风格的 `Question → FINAL ANSWER`，20 题全部作为测试集，程序执行准精确匹配评分。

仓库只发布实验代码、协议、测试、依赖锁和复现说明。正式问题、标准答案、aliases、来源字段、模型回复、运行日志和实验结果均从父仓库在本地读取，且被 Git 忽略。

## 六个实验架构

| ID | 架构 | 本任务线中的框架特征 |
| --- | --- | --- |
| T1 | Direct | 单次模型请求；确定性注入完整公开知识快照；无工具 |
| T2 | LangGraph | `create_agent` 流式 ReAct；与建模线相同的只读技能和知识工具，无写文件 |
| T3 | smolagents | `CodeAgent`，`tools=[]`；解释器放行 `json`、`pathlib`，自己读知识目录 |
| T4 | OpenHands | 原生 `invoke_skill`；官方终端、文件编辑器和任务跟踪；浏览器关闭 |
| T5 | CrewAI | `Crew(skills=...)`，允许委派；官方文件工具；复核者只读 |
| T6 | OSIS-AI | 不另起服务；调用父仓库 `datasets/qa/run_eval.py` 的 `chat_via_agent`；强制串行 |

T6 复用父仓库问答代理，读的是父仓库 OpenCode 里的技能。T1–T5 拿到这棵技能树的完整副本，题面仍是同一个 `Question` 和 system prompt。`task_id`、category、gold、aliases 与 source 留在统一 runner 内，用于运行标识、分组和评分。

框架细节见 [docs/框架使用说明.md](docs/框架使用说明.md)。环境见 [ENVIRONMENT.md](ENVIRONMENT.md)。

## 快速验证

```powershell
uv sync --python 3.13 --extra test
uv run pytest -q
uv run python scripts/audit_public_boundary.py
```

配置父仓库后，只读取题号和分类做协议检查：

```powershell
uv run python scripts/run_dataset.py `
  --parent-repo C:\path\to\osis-skill-enhance `
  --architecture T2 `
  --skills-dir tmp\qa-knowledge-snapshot `
  --dry-run
```

完整复现步骤见 [REPRODUCIBILITY.md](REPRODUCIBILITY.md)。

## 评分

- `accuracy`：抽取最后一个 `FINAL ANSWER:`，按父仓库规则做数字、列表、接口路径、别名和中英文是非答案的准精确匹配。
- `efficiency = 1 / (1 + mean_generation_elapsed_s / 240)`。
- `overall = 0.80 × accuracy + 0.20 × efficiency`。

模型调用失败、超时或没有最终答案的题仍进入分母，accuracy 记 0；其实际生成耗时仍进入 efficiency。

正式汇总按架构先计算整套题准确率和平均耗时，再计算综合分。结果默认写入 `runs/` 与 `results/`，不会进入版本库。

## 发布边界

禁止提交 `datasets/`、`questions.json`、`runs/`、`reports/`、`results/`、`private/`、`tmp/`、本机父仓库路径和任何凭据。发布前运行：

```powershell
uv run python scripts/audit_public_boundary.py
```

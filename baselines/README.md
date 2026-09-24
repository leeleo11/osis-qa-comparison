# Baselines

每个目录都提供统一入口：

```text
python -m baselines.<adapter>.adapter --request <adapter_request.json>
```

适配器只把 `Question`、system prompt、知识快照和模型配置交给模型，随后写 `<tN>_generation.json`。task_id/category 留在 runner 与运行清单中；统一 runner 在框架进程退出后读取结果并访问私有 gold 评分。

T1–T5 读取父仓库技能树的完整副本，和 T6 在父仓库 OpenCode 里能打开的是同一批文件。T1 把这批文件放进一次请求。T2 用只读工具按需读取。T3 用 `pathlib` 读取。T4 用 OpenHands 原生技能、终端和文件编辑器。T5 用 CrewAI 原生技能挂载、委派和文件工具。T6 只调用父仓库问答评测的 `chat_via_agent`。

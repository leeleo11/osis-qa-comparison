# Baselines

每个目录都提供统一入口：

```text
python -m baselines.<adapter>.adapter --request <adapter_request.json>
```

适配器只把 `Question`、system prompt、知识快照和模型配置交给模型，随后写 `<tN>_generation.json`。task_id/category 留在 runner 与运行清单中；统一 runner 在框架进程退出后读取结果并访问私有 gold 评分。

T1–T5 读取父仓库技能树的完整副本。T2–T5 用同一对只读函数 `list_knowledge_bases` 和 `hybrid_search`，密钥来自父仓库 OpenCode 配置或 `WEKNORA_API_KEY`，不走会话或 `agent-chat`。T1 没有工具循环。T3 不放行 `pyosis`。T6 调用父仓库问答评测的 `chat_via_agent`，检索留在父仓库已经运行的会话里。工具差异见 `docs/框架使用说明.md`。

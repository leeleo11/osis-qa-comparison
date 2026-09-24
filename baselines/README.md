# Baselines

每个目录都提供统一入口：

```text
python -m baselines.<adapter>.adapter --request <adapter_request.json>
```

适配器只把 `Question`、system prompt、知识快照和模型配置交给模型，随后写 `<tN>_generation.json`。task_id/category 留在 runner 与运行清单中；统一 runner 在框架进程退出后读取结果并访问私有 gold 评分。

T1–T5 读取父仓库技能树的完整副本。T2–T5 另外用父仓库 OpenCode 的检索密钥调用 `list_knowledge_bases` 和 `hybrid_search`，不走会话或 `agent-chat`。T6 调用父仓库问答评测的 `chat_via_agent`。

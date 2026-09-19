# Baselines

每个目录都提供统一入口：

```text
python -m baselines.<adapter>.adapter --request <adapter_request.json>
```

适配器只把 `Question`、system prompt、知识快照和模型配置交给模型，随后写 `<tN>_generation.json`。task_id/category 留在 runner 与运行清单中；统一 runner 在框架进程退出后读取结果并访问私有 gold 评分。

T1 的知识通过固定 prompt bundle 注入；T2/T3/T5 使用同一组三个只读工具；T4 由 OpenHands 原生加载 AgentSkills；T6 在隔离 OpenCode 项目内原生发现技能。

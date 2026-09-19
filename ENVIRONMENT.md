# Environment

## Python

- Python `>=3.13,<3.14`
- 基础：`httpx`、`requests`、`PyYAML`、父协议使用的 `opencode-ai==0.1.0a36`
- T2：LangGraph / LangChain OpenAI
- T3：smolagents
- T4：OpenHands SDK
- T5：CrewAI
- T6：OpenCode / OSIS-AI 原生运行时

精确解析结果由 `uv.lock` 固定。框架依赖分环境安装，避免 LangChain、LiteLLM、Pydantic 等传递依赖互相覆盖。

## QA 任务不需要 OSIS 求解器

本任务线只做文档与 API 问答，不启动 OSIS 建模或验算。T6 仍使用 OSIS-AI 的原生 OpenCode 工作流，以保留产品框架能力。

## 网络与凭据

- `OSIS_MODEL_API_KEY`：模型网关密钥，只通过环境变量传入。
- `OSIS_MODEL_BASE_URL`：OpenAI 兼容 `/v1` 地址。
- `OPENCODE_EXE`：可选，T6 的 OpenCode 可执行文件。
- `OSIS_AGENTS_FILE`：可选，显式指定 OSIS-AI 原生 `AGENTS.md`；默认使用父仓库版本。
- `NO_PROXY/no_proxy`：T6 自动补充 `127.0.0.1,localhost,::1`。

凭据不会写入 request、manifest、日志、配置或结果；T6 的配置只保留 `{env:OSIS_MODEL_API_KEY}` 引用。T6 子进程会移除其它 `*_API_KEY`、父仓库位置与常见仓库令牌。

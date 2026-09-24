# Environment

## Python

- Python `>=3.13,<3.14`
- 基础：`httpx`、`requests`、`PyYAML`、父协议使用的 `opencode-ai==0.1.0a36`
- T2：LangGraph / LangChain OpenAI
- T3：smolagents
- T4：OpenHands SDK
- T5：CrewAI
- T6：父仓库已经在运行的 OpenCode。本仓库不安装、不启动、不改权限

精确解析结果由 `uv.lock` 固定。框架依赖分环境安装，避免 LangChain、LiteLLM、Pydantic 等传递依赖互相覆盖。

## QA 任务不需要 OSIS 求解器

本任务线只做文档与 API 问答，不启动 OSIS 建模或验算。T6 直接调用父仓库 `datasets/qa/run_eval.py` 的 `chat_via_agent`，因此使用父仓库自己的 OpenCode、技能和权限。

## 网络与凭据

- `OSIS_MODEL_API_KEY`：模型网关密钥，只通过环境变量传入。
- `OSIS_MODEL_BASE_URL`：OpenAI 兼容 `/v1` 地址。
- `WEKNORA_API_KEY`：可选。不设时使用父仓库 OpenCode 里的检索密钥。不要改用只能建会话的用户密钥。
- `WEKNORA_BASE_URL`：可选。不设时使用父仓库配置，否则默认 `https://knowledge.osisbim.com/api/v1`。
- 父仓库 OpenCode 须已按父仓库问答评测的方式启动，默认 `http://127.0.0.1:4096`。T6 使用那里已经挂好的 WeKnora MCP。本仓库不读取 `OPENCODE_EXE`，也不写 OpenCode 权限配置。

凭据不会写入 request、manifest、日志或结果。

# A2A-ChatHub

`A2A-ChatHub` 是一个面向多智能体协作的 Python 项目骨架。它围绕统一的 A2A 风格 JSON 消息协议实现了：

- 多 Agent 消息路由
- CLI 对话演示
- WebSocket 通信层
- JSON 日志落盘
- 可开关的规则模式 / 真实模型模式

项目内置两个示例 Agent：`Alice` 和 `Bob`。默认情况下项目只演示消息流；当你显式启用 live backend 时，它也可以接入真实模型回答用户问题。

## 功能概览

- 支持多 Agent 通过 `Coordinator` 路由通信
- 统一消息格式：`sender / receiver / timestamp / content`
- 支持 `rule` 模式和 `openai` / `local` / `auto` 模式
- 提供 CLI 交互入口
- 提供可选 WebSocket Server / Client
- 自动将所有消息写入 `logs/messages.json`

## 项目结构

```text
A2A-ChatHub/
|- agents/
|  |- __init__.py
|  |- base_agent.py
|  `- example_agent.py
|- coordinator/
|  |- __init__.py
|  `- coordinator.py
|- frontend/
|  |- __init__.py
|  `- cli.py
|- llm/
|  |- __init__.py
|  `- client.py
|- logs/
|  `- messages.json
|- protocol/
|  |- __init__.py
|  `- websocket_protocol.py
|- LICENSE
|- main.py
|- README.md
`- requirements.txt
```

## 消息格式

所有消息统一使用以下 JSON 结构：

```json
{
  "sender": "Alice",
  "receiver": "Bob",
  "timestamp": "2026-03-15T03:53:04.647200+00:00",
  "content": "Hello from Alice"
}
```

字段说明：

- `sender`：发送方
- `receiver`：接收方
- `timestamp`：ISO 8601 时间戳
- `content`：消息正文

## 运行模式

### 1. Rule 模式

默认模式，不调用真实模型，只演示多 Agent 消息流。

典型链路：

`User -> Alice -> Bob -> Alice -> Bob`

启动方式：

```bash
python main.py
```

或显式指定：

```bash
python main.py --backend rule
```

### 2. Live 模式

显式启用后，项目会调用真实的 OpenAI 兼容接口。

典型链路：

`User -> Alice -> Bob -> Alice -> User`

其中：

- `Alice` 负责接收用户请求并协调
- `Bob` 负责生成中间草稿
- `Alice` 汇总后返回最终答案给 `User`

支持的 live backend：

- `openai`
- `local`
- `auto`

## 快速开始

### 1. 创建虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

当前项目唯一强制依赖是：

- `websockets`

说明：

- WebSocket 功能依赖 `websockets`
- 模型调用通过标准库 `urllib` 实现，不依赖 `openai` SDK

### 3. 运行演示

只运行一轮 Alice / Bob 示例：

```bash
python main.py --demo-only
```

进入交互式 CLI：

```bash
python main.py
```

退出：

```text
exit
```

或：

```text
quit
```

## Live Backend 配置

真实模型调用由 [llm/client.py](e:/Desktop/A2A-ChatHub/llm/client.py) 负责，底层请求的是 OpenAI 兼容的 `chat/completions` 接口。

### OpenAI

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY="your_api_key"
python main.py --backend openai --model gpt-4.1-mini
```

可选：

```powershell
python main.py --backend openai --model gpt-4.1-mini --demo-only
```

说明：

- `OPENAI_API_KEY` 必填
- `--model` 可改成你要使用的模型
- 默认请求地址为 `https://api.openai.com/v1`

### Local OpenAI-Compatible Backend

适用于以下本地服务：

- Ollama
- LM Studio
- llama.cpp server
- vLLM-compatible API
- 其他兼容 OpenAI Chat Completions 的服务

Windows PowerShell：

```powershell
$env:A2A_BASE_URL="http://127.0.0.1:11434/v1"
$env:A2A_MODEL_NAME="qwen2.5:7b-instruct"
python main.py --backend local
```

如果服务需要 Key：

```powershell
$env:A2A_API_KEY="your_local_key"
```

也可以直接通过参数覆盖：

```powershell
python main.py --backend local --base-url http://127.0.0.1:11434/v1 --model qwen2.5:7b-instruct
```

### Auto 模式

```bash
python main.py --backend auto
```

选择顺序：

1. 如果存在 `OPENAI_API_KEY`，优先走 `openai`
2. 否则如果存在 `A2A_BASE_URL`，走 `local`
3. 否则回退到 `rule`

## CLI 参数

[main.py](e:/Desktop/A2A-ChatHub/main.py) 当前支持：

- `--demo-only`：只跑内置示例后退出
- `--with-server`：启动可选 WebSocket Server
- `--host`：WebSocket Server 地址，默认 `127.0.0.1`
- `--port`：WebSocket Server 端口，默认 `8765`
- `--backend`：`rule`、`openai`、`local`、`auto`
- `--model`：覆盖 live backend 的模型名
- `--base-url`：覆盖 live backend 的接口地址

## WebSocket 支持

协议层在 [protocol/websocket_protocol.py](e:/Desktop/A2A-ChatHub/protocol/websocket_protocol.py)。

当前提供：

- `WebSocketA2AServer`
- `WebSocketA2AClient`
- 事件订阅 / 推送机制

启动 Server：

```bash
python main.py --with-server
```

自定义地址：

```bash
python main.py --with-server --host 127.0.0.1 --port 8765
```

## 核心模块说明

### Agent

[agents/base_agent.py](e:/Desktop/A2A-ChatHub/agents/base_agent.py)

- 定义 Agent 基类
- 提供 `send_message`
- 提供 `receive_message`
- 提供可重写的 `respond`

[agents/example_agent.py](e:/Desktop/A2A-ChatHub/agents/example_agent.py)

- 在 `rule` 模式下执行规则回复
- 在 live 模式下执行 Alice / Bob 协作回答
- 保留了后续扩展更多 Agent 的接口

### Coordinator

[coordinator/coordinator.py](e:/Desktop/A2A-ChatHub/coordinator/coordinator.py)

负责：

- 注册 Agent
- 按 `receiver` 路由消息
- 保存全量历史
- 保存按 Agent 划分的上下文
- 将所有消息写入 `logs/messages.json`

### CLI

[frontend/cli.py](e:/Desktop/A2A-ChatHub/frontend/cli.py)

负责：

- 启动内置示例
- 展示消息流
- 接收用户输入
- 把消息交给 Coordinator

## 日志与回放

所有路由过的消息都会写入：

- [logs/messages.json](e:/Desktop/A2A-ChatHub/logs/messages.json)

用途包括：

- 还原一次完整对话
- 调试 Agent 间协作过程
- 分析 prompt 与路由行为
- 后续扩展回放工具

## 自定义扩展

如果你要新增 Agent，推荐方式：

1. 继承 `BaseAgent`
2. 重写 `respond()`
3. 在 [main.py](e:/Desktop/A2A-ChatHub/main.py) 中注册

如果你要新增模型供应商，推荐方式：

1. 在 [llm/client.py](e:/Desktop/A2A-ChatHub/llm/client.py) 中添加适配逻辑
2. 保持输出仍然兼容当前消息结构
3. 不改 Coordinator 的路由层

## 当前限制

- `rule` 模式只演示消息流，不会回答真实问题
- live 模式依赖外部模型服务可用
- 当前日志是顺序追加式 JSON 数组，不是数据库

## License

项目使用 MIT License，见 [LICENSE](e:/Desktop/A2A-ChatHub/LICENSE)。

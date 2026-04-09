# Lizziezy LLM 控制中枢 / Lizziezy LLM Control Hub

一个给 Lizziezy 发行包使用的「自然语言控制 + 实时对话」外置控制层。  
An external control layer for the Lizziezy distribution, combining natural-language commands and real-time chat.

你可以把它理解为 / In short, this project provides:
- 前端聊天面板（WebSocket + HTTP）/ Frontend chat panel (WebSocket + HTTP)
- FastAPI 控制服务 / FastAPI backend service
- 对 Lizziezy 配置文件与进程的自动化控制 / Automated control of Lizziezy config and process
- 对最新棋谱的实时 KataGo 局势分析 / Real-time KataGo analysis on latest SGF

> 说明 / Note: 本项目面向 Lizziezy 发行包集成，不依赖 Lizziezy Java 源码。  
> This project is built for distribution-level integration and does not require Lizziezy Java source code.

## 功能特性 / Features

- 自然语言控制（启动/停止/重启/状态/难度/每手用时/visits）  
	Natural-language control (start/stop/restart/status/difficulty/move time/visits)
- 聊天与控制一体（同一输入框）  
	Chat and command execution in one input box
- 实时局势分析（胜率、目差、候选点、PV、趋势、复杂度）  
	Real-time position analysis (winrate, score lead, candidates, PV, trend, complexity)
- 试下并评价（指定点位或自动点位）  
	Try-move evaluation (manual point or automatic candidate)
- OpenAI 兼容接口接入  
	OpenAI-compatible API integration
- 双通道调用：`/ws/chat` 与 `POST /api/chat-command`  
	Dual channels: `/ws/chat` and `POST /api/chat-command`

## 项目结构 / Project Structure

```text
llm_control/
|- app.py                   # FastAPI backend
|- frontend/index.html      # Web UI
|- .env.example             # Environment template
|- requirements.txt         # Python dependencies
`- Start-LLM-Control.bat    # One-click startup on Windows
```

## 环境要求 / Requirements

- Windows（当前发行包场景默认）/ Windows (distribution scenario)
- Python 3.10+
- 可运行的 Lizziezy 发行包目录 / A runnable Lizziezy distribution directory
- 可用的 KataGo 可执行文件、模型与 analysis 配置  
	Available KataGo executable, model, and analysis config

## 快速开始 / Quick Start

### 1) 安装依赖 / Install dependencies

在 `llm_control` 目录执行 / Run in the `llm_control` directory:

```bash
pip install -r requirements.txt
```

### 2) 配置环境变量 / Configure environment

复制 `.env.example` 为 `.env`，至少填写 / Copy `.env.example` to `.env` and fill at least:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_key_here
LLM_MODEL=gpt-4.1-mini
```

如果目录结构不同，请修改这些路径 / If your folders differ, update:

- `LIZZIE_EXE`
- `LIZZIE_CONFIG`
- `LIZZIE_WORKDIR`
- `LIZZIE_SAVE_DIR`
- `POSITION_KATAGO_PATH`
- `POSITION_MODEL_PATH`
- `POSITION_CONFIG_PATH`

### 3) 启动服务 / Start service

```bat
Start-LLM-Control.bat
```

默认地址 / Default endpoints:

- Web UI: `http://127.0.0.1:18100`
- Health: `http://127.0.0.1:18100/api/health`

## 环境变量说明 / Environment Variables

| 变量名 / Variable | 说明 / Description | 默认值 / Default |
|---|---|---|
| `LLM_BASE_URL` | OpenAI 兼容接口地址 / OpenAI-compatible API base URL | `https://api.openai.com/v1` |
| `LLM_API_KEY` | 模型服务密钥 / Model API key | 空 / Empty |
| `LLM_MODEL` | 聊天模型名 / Chat model name | `gpt-4.1-mini` |
| `LIZZIE_EXE` | Lizziezy 可执行文件路径 / Lizziezy executable path | `../Lizzieyzy-2.5.3-win64.exe` |
| `LIZZIE_CONFIG` | Lizziezy 配置文件路径 / Lizziezy config path | `../config.txt` |
| `LIZZIE_WORKDIR` | Lizziezy 工作目录 / Lizziezy working dir | `..` |
| `LIZZIE_SAVE_DIR` | 棋谱目录 / SGF directory | `../save` |
| `POSITION_KATAGO_PATH` | 分析用 KataGo 路径 / KataGo path for analysis | `../katago_eigen/katago.exe` |
| `POSITION_MODEL_PATH` | 分析模型路径 / Analysis model path | `../weights/kata15bs167.bin.gz` |
| `POSITION_CONFIG_PATH` | 分析配置路径 / Analysis config path | `../katago_configs/analysis.cfg` |
| `POSITION_RULES` | 规则 / Rules | `chinese` |
| `POSITION_MAX_VISITS` | 最大 visits / Max visits | `120` |
| `POSITION_MAX_TIME` | 最大分析时长（秒）/ Max analysis time (s) | `1.5` |

## API 速览 / API Overview

### `GET /api/health`

返回服务状态与 LLM 配置情况。  
Returns backend status and LLM configuration state.

关键字段 / Key fields:
- `status`
- `running`
- `llm_configured`
- `llm_base_url`
- `llm_model`

### `GET /api/position`

返回最新局势分析。  
Returns latest position analysis.

关键字段 / Key fields:
- `phase`
- `winrate`
- `scoreLead`
- `recommendations`
- `main_pv`
- `complexity`
- `trend`

### `POST /api/chat-command`

请求示例 / Request example:

```json
{
	"message": "难度调到困难并把每手设为4秒"
}
```

响应示例 / Response example:

```json
{
	"ok": true,
	"message": "已切到困难难度。难度已设为 hard（visits=2500, 每手用时=5.0s）。",
	"action": "set_difficulty",
	"data": {
		"source": "fallback",
		"level": "hard",
		"visits": 2500,
		"think": 5.0
	}
}
```

## 常用自然语言命令 / Common Commands

- `启动 lizziezy` / `start lizziezy`
- `停止 lizziezy` / `stop lizziezy`
- `重启 lizziezy` / `restart lizziezy`
- `难度调到困难` / `set difficulty to hard`
- `每手用时 4 秒` / `set move time to 4 seconds`
- `visits 3000`
- `设置 leelaz.play-ponder = true` / `set leelaz.play-ponder = true`
- `试下 D4 并评价` / `try D4 and evaluate`
- `按当前局势自动试下一手并评价` / `auto try one move and evaluate`

## 常见问题 / FAQ

### 1) 页面可打开但无法分析局势 / UI opens but no analysis

- 检查 `LIZZIE_SAVE_DIR` 下是否有 `.sgf`  
	Check if `.sgf` exists in `LIZZIE_SAVE_DIR`
- 检查 `POSITION_KATAGO_PATH`、`POSITION_MODEL_PATH`、`POSITION_CONFIG_PATH`  
	Verify `POSITION_KATAGO_PATH`, `POSITION_MODEL_PATH`, and `POSITION_CONFIG_PATH`

### 2) 聊天总是走 fallback / Chat always falls back

- 检查 `LLM_API_KEY` 是否填写  
	Confirm `LLM_API_KEY` is set
- 检查 `LLM_BASE_URL` 可访问性  
	Confirm `LLM_BASE_URL` is reachable
- 检查 `/api/health` 中 `llm_configured` 是否为 `true`  
	Confirm `llm_configured=true` in `/api/health`

### 3) 控制命令执行失败 / Command execution fails

- 检查 `LIZZIE_EXE` 路径  
	Check `LIZZIE_EXE` path
- 检查 `config.txt` 是否是有效 JSON  
	Check whether `config.txt` is valid JSON

## 开发说明 / Development

开发模式（热重载）/ Dev mode (hot reload):

```bash
uvicorn app:app --host 127.0.0.1 --port 18100 --reload
```

如仓库内有多个后端服务，请避免端口冲突。  
If you run multiple backend services in the same repo, avoid port conflicts.

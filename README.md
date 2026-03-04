# AI-Digest

一个本地优先的 CLI 工具，自动采集你每天使用各种 AI 编程助手的会话记录，生成结构化的每日工作摘要。

## 特性

- **多源数据采集** — 支持 5 种主流 AI 编程工具的本地日志解析
  - [Claude Code](https://claude.ai) (JSONL)
  - [Codex](https://openai.com/codex) (JSONL)
  - [Antigravity](https://google.com) (Artifacts + Metadata)
  - [OpenCode](https://github.com/nicholasgasior/opencode) (Workspace DAT)
  - [Gemini CLI](https://github.com/google-gemini/gemini-cli) (History Dir)
- **LLM 智能分析** — 将原始日志发送给大模型，自动聚合、归类、生成中文每日报告
- **零外部依赖调用** — 使用 Python 原生 `urllib` 直接调用 OpenAI / Anthropic 兼容 API
- **本地时区感知** — 自动将 UTC 时间戳转换为系统本地时区

## 安装

```bash
# 推荐使用 uv
uv sync

# 或者 pip
pip install -e .
```

## 使用

### 采集会话数据

```bash
# 采集今天的 AI 会话记录
digest collect

# 采集指定日期
digest collect --date 2026-03-03
```

### 生成 AI 分析报告

```bash
# 需要先配置 config.yaml
digest analyze --date 2026-03-03
```

## 配置

复制示例配置文件并填入你的 LLM API 信息：

```bash
cp config.example.yaml config.yaml
```

```yaml
ai:
  api_key: "your-api-key"
  model: "gpt-4o-mini"
  base_url: "https://api.openai.com/v1"  # 可选，自定义 endpoint
  provider: "openai"                      # openai | anthropic
```

支持任何 OpenAI 或 Anthropic 兼容的 API 服务。

## 数据源路径

| 工具 | 本地日志路径 | 格式 |
|------|-------------|------|
| Claude Code | `~/.claude/projects/` | JSONL (明文) |
| Codex | `~/.codex/sessions/` | JSONL (明文) |
| Antigravity | `~/.gemini/antigravity/brain/` | Artifacts + JSON metadata |
| OpenCode | `~/Library/Application Support/ai.opencode.desktop/` | JSON DAT |
| Gemini CLI | `~/.gemini/history/` | Directory mtime |

## 输出示例

### `digest collect`
```
Activity Timeline
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Time          ┃ Source      ┃ Project  ┃ Title             ┃ Msgs ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ 13:30 - 13:34 │ Claude Code │ my-app   │ Implementing auth │   14 │
│ 14:32 - 14:44 │ Codex       │ blog     │ Writing new post  │   19 │
└───────────────┴─────────────┴──────────┴───────────────────┴──────┘
```

### `digest analyze`

通过 LLM 自动聚合生成的结构化报告，包含：
- **Highlights** — 当天工作亮点概述
- **Activities** — 按时间线聚合的活动卡片，含项目、分类、详细要点

## 技术栈

- Python 3.11+
- [Pydantic](https://docs.pydantic.dev/) — 数据模型验证
- [Rich](https://rich.readthedocs.io/) — 终端美化输出
- [PyYAML](https://pyyaml.org/) — 配置文件解析
- `urllib` — 零依赖 HTTP 请求

## License

MIT

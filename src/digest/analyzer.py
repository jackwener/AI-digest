from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import date
from typing import List, Optional

from digest.config import DigestConfig
from digest.models import NormalizedSession, DailySummary


class Analyzer:
    MAX_CONTEXT_CHARS = 60000

    def __init__(self, config: DigestConfig):
        self.config = config

    def analyze(self, target_date: date, sessions: List[NormalizedSession]) -> Optional[DailySummary]:
        if not sessions:
            return None

        context_text = self._build_context_text(sessions)

        system_prompt = f"""
你是一位专业的工程效率分析师。请分析用户当天与各 AI Agent 的交互日志，生成一份详细的中文每日工作摘要。
日期：{target_date.isoformat()}

规则：
1. 忽略无意义的交互（如只说了"hi"或空对话）。
2. 将相关会话按时间线或项目聚合为"活动（Activity）"。
3. 每个活动的 summary 要简洁概括做了什么事。
4. **details 必须详细列出该活动中具体做的每一个要点**，不能笼统带过。例如：修改了哪些文件、实现了什么功能、讨论了什么技术概念、产出了什么文档等。至少列出 3-5 个要点。
5. 如果日志中项目名缺失，请根据上下文推断项目或仓库名（如 "mega-reth"、"blog"、"digest"）。实在推断不出就填 "-"。
6. highlights 提供 1-2 句当天整体亮点概述。
7. 所有文本内容（summary、details、highlights 等）必须使用中文。技术术语保留英文。
8. 必须输出合法 JSON，匹配以下 schema，不要包含 markdown 代码块。

JSON 输出格式示例：
{{
  "date": "2026-03-04",
  "highlights": ["全天主要围绕 MegaETH 技术文档撰写和 digest CLI 工具开发"],
  "activities": [
    {{
      "time_range": "09:00 - 11:30",
      "project": "digest",
      "category": "coding",
      "summary": "实现了基于 LLM 的每日活动分析引擎",
      "details": [
        "编写了 config.yaml 配置解析逻辑，支持 api_key / model / base_url / provider",
        "基于 urllib 封装了 OpenAI / Anthropic 兼容的 HTTP 请求",
        "设计了 DailySummary / ActivityItem Pydantic 模型",
        "编写 system prompt 约束 JSON 输出格式",
        "添加了 markdown 代码块自动剥离逻辑以兼容不规范模型输出"
      ]
    }}
  ]
}}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Logs:\n{context_text}"}
        ]

        provider = self.config.ai.provider.lower()
        api_key = self.config.ai.api_key
        base_url = self.config.ai.base_url
        model_name = self.config.ai.model

        if provider == "anthropic":
            endpoint = base_url or "https://api.anthropic.com"
            if not endpoint.endswith("/v1/messages") and not endpoint.endswith("/messages"):
                if not endpoint.endswith("/"):
                    endpoint += "/"
                endpoint += "v1/messages"
            
            # Anthropic expects 'system' at top level, not in messages
            system_txt = system_prompt
            anthropic_msgs = [{"role": "user", "content": f"Logs:\n{context_text}"}]
            
            payload = {
                "model": model_name,
                "system": system_txt,
                "messages": anthropic_msgs,
                "max_tokens": 4096
            }
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            }
        else:
            # Default to OpenAI compatible
            endpoint = base_url or "https://api.openai.com/v1"
            if not endpoint.endswith("/chat/completions") and not endpoint.endswith("/completions"):
                if not endpoint.endswith("/"):
                    endpoint += "/"
                endpoint += "chat/completions"
                
            payload = {
                "model": model_name,
                "messages": messages,
                "response_format": {"type": "json_object"}
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            error_msg = str(e)
            if hasattr(e, 'read'):
                try:
                    error_msg += f" - {e.read().decode('utf-8')}"
                except Exception:
                    pass
            print(f"\nAPI Request Failed: {error_msg}")
            return None

        # Extract content based on provider
        try:
            if provider == "anthropic":
                content = result["content"][0]["text"]
            else:
                content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            print(f"\nUnexpected API response structure: {result}")
            return None
        if not content:
            return None

        # Strip markdown formatting if the model returned ```json ... ```
        clean_content = content.strip()
        if clean_content.startswith("```json"):
            clean_content = clean_content[7:]
        elif clean_content.startswith("```"):
            clean_content = clean_content[3:]
        if clean_content.endswith("```"):
            clean_content = clean_content[:-3]
        clean_content = clean_content.strip()

        # Parse the JSON response
        try:
            data = json.loads(clean_content)
            return DailySummary(**data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse LLM response: {e}\nRaw output: {content}")
            return None

    def _build_context_text(self, sessions: List[NormalizedSession]) -> str:
        context_lines = []
        remaining = self.MAX_CONTEXT_CHARS

        for session in sessions:
            time_str = session.start_time.strftime("%H:%M")
            project_str = f" | Project: {session.project_path}" if session.project_path else ""
            header = (
                f"[{time_str}] Source: {session.source}{project_str}\n"
                f"Title/Summary: {session.title_or_prompt}\n"
                f"Messages: {session.message_count}\n"
            )
            if len(header) >= remaining:
                break

            context_lines.append(header)
            remaining -= len(header)

            if session.full_context and remaining > 0:
                block_prefix = "Detailed Content:\n"
                if len(block_prefix) < remaining:
                    snippet, truncated = self._truncate_text(session.full_context, remaining - len(block_prefix) - 1)
                    block = f"{block_prefix}{snippet}\n"
                    context_lines.append(block)
                    remaining -= len(block)

            separator = "---"
            if len(separator) >= remaining:
                break
            context_lines.append(separator)
            remaining -= len(separator) + 1

            if remaining <= 0:
                break

        return "\n".join(context_lines)

    def _truncate_text(self, text: str, available: int) -> tuple[str, bool]:
        suffix = "\n...[Truncated]"
        if available <= 0:
            return "", bool(text)
        if len(text) <= available:
            return text, False
        if available <= len(suffix):
            return suffix[:available], True
        return text[: available - len(suffix)].rstrip() + suffix, True

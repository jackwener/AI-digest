import json
import urllib.request
import urllib.error
from datetime import date
from typing import List

from digest.config import DigestConfig
from digest.models import NormalizedSession, DailySummary


class Analyzer:
    def __init__(self, config: DigestConfig):
        self.config = config

    def analyze(self, target_date: date, sessions: List[NormalizedSession]) -> DailySummary | None:
        if not sessions:
            return None

        # Prepare context
        context_lines = []
        for s in sessions:
            time_str = s.start_time.strftime("%H:%M")
            project_str = f" | Project: {s.project_path}" if s.project_path else ""
            context_str = (
                f"[{time_str}] Source: {s.source}{project_str}\n"
                f"Title/Summary: {s.title_or_prompt}\n"
                f"Messages: {s.message_count}\n"
            )
            if s.full_context:
                context_str += f"Detailed Content:\n{s.full_context}\n"
            context_str += "---"
            context_lines.append(context_str)
        
        context_text = "\n".join(context_lines)

        system_prompt = f"""
You are an expert engineering productivity analyst. Your task is to analyze the daily AI agent interaction logs for the user.
Today's date is {target_date.isoformat()}.

Rules:
1. Ignore trivial pings (e.g., just saying "hi" or empty chats).
2. Cluster related sessions chronologically or by project into cohesive "Activities".
3. An activity should describe the meaningful work done (e.g., "Implemented feature X in project Y", "Researched concepts about Z").
4. If a project name is missing or "N/A" in the logs, you MUST carefully try to infer the relevant project or repository name from the activity's context or topic (e.g., "mega-reth", "blog", "digest"). If you absolutely cannot infer any project name, output "-" instead of "N/A" or "None".
5. Provide a 1-2 sentence overall highlight for the day.
6. You MUST output your response in valid JSON matching the schema of the DailySummary. Do not include markdown codeblocks or extra text.

Example JSON output structure:
{{
  "date": "2026-03-04",
  "highlights": ["Spent most of the day researching and implementing Phase 2.", ...],
  "activities": [
    {{
      "time_range": "09:00 - 11:30",
      "project": "digest",
      "category": "coding",
      "summary": "Implemented AI Analyzer using litellm",
      "details": ["Added config parsing", "Integrated OpenAI API"]
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

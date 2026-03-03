import json
from datetime import date
from typing import List

from litellm import completion

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
            context_lines.append(
                f"[{time_str}] Source: {s.source} | Project: {s.project_path or 'N/A'}\n"
                f"Topic: {s.title_or_prompt}\n"
                f"Messages: {s.message_count}\n"
                f"---"
            )
        
        context_text = "\n".join(context_lines)

        system_prompt = f"""
You are an expert engineering productivity analyst. Your task is to analyze the daily AI agent interaction logs for the user.
Today's date is {target_date.isoformat()}.

Rules:
1. Ignore trivial pings (e.g., just saying "hi" or empty chats).
2. Cluster related sessions chronologically or by project into cohesive "Activities".
3. An activity should describe the meaningful work done (e.g., "Implemented feature X in project Y", "Researched concepts about Z").
4. Provide a 1-2 sentence overall highlight for the day.
5. You MUST output your response in valid JSON matching the schema of the DailySummary. Do not include markdown codeblocks or extra text.

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

        response = completion(
            model=getattr(self.config.ai, "model_override", f"{self.config.ai.provider}/{self.config.ai.model}"),
            messages=messages,
            api_key=self.config.ai.api_key,
            api_base=self.config.ai.base_url,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
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

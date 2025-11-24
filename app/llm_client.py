"""
LLM client wrapper for generating SQL from prompts.

This file:
- Loads your OPENAI_API_KEY from the environment
- Provides a simple function `generate_sql(prompt: str)`
- Makes it easy to switch models later
"""

from __future__ import annotations
import os
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

# Load .env if present
load_dotenv()

class LLMClient:
    """
    A thin wrapper over OpenAI's Chat Completions API.
    """

    def __init__(
        self,
        model: str = "gpt-4.1",       # Good default. You can switch to gpt-4o-mini for cheaper testing.
        temperature: float = 0.0,     # 0 for deterministic SQL generation
    ):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Set it in your .env file.")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature

    def generate_sql(self, prompt: str) -> str:
        """
        Send a full prompt (system rules + schema + examples + question) to the LLM.
        Returns the raw SQL string from the model.

        The caller is responsible for passing this SQL into sql_guard.
        """

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": "You are a skilled SQL generator."},
                {"role": "user", "content": prompt},
            ],
        )

        raw = response.choices[0].message.content

        # Strip code blocks if present (many models wrap in ```sql ... ```)
        cleaned = _strip_code_fences(raw)
        return cleaned


def _strip_code_fences(text: str) -> str:
    """
    Remove ```sql ... ``` or ``` blocks.
    """
    if text is None:
        return ""

    t = text.strip()
    if t.startswith("```"):
        # remove first fence
        t = t.split("```", 1)[1]
        # remove second fence
        if "```" in t:
            t = t.split("```", 1)[0]
    return t.strip()

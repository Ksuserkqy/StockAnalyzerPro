from __future__ import annotations

from typing import Iterable, Dict, Any
from openai import OpenAI

from config import settings


class DeepSeekLLM:
    def __init__(self):
        # DeepSeek API：OpenAI 兼容 base_url / api_key 用法
        # 参考 DeepSeek 官方文档：base_url=https://api.deepseek.com 或 /v1 :contentReference[oaicite:3]{index=3}
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    def stream_chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> Iterable[str]:
        """
        以 token 流形式产出文本片段（console/GUI 都能接）
        """
        stream = self.client.chat.completions.create(
            model=settings.deepseek_model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and getattr(delta, "content", None):
                yield delta.content

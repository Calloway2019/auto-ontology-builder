"""LLM Client - OpenAI SDK compatible async client."""

import json
import logging
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async LLM client wrapping OpenAI SDK for any compatible model."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = base_url or settings.LLM_BASE_URL
        self.model = model or settings.LLM_MODEL_NAME
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=settings.LLM_TIMEOUT,
            )
        return self._client

    def refresh_client(self, api_key: str, base_url: str, model: str):
        """Update client configuration dynamically."""
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = None  # Force re-creation

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion request and return the text response."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                logger.info(
                    "LLM call success: model=%s, tokens_used=%s",
                    self.model,
                    response.usage.total_tokens if response.usage else "N/A",
                )
                return content
            except Exception as e:
                logger.warning("LLM call attempt %d failed (base_url=%s): %s", attempt + 1, self.base_url, str(e))
                if attempt == max_retries - 1:
                    raise
        return ""

    async def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """Send a chat completion request expecting JSON output."""
        content = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        return self._parse_json(content)

    async def test_connection(self) -> dict:
        """Test LLM connectivity. Returns status dict."""
        try:
            response = await self.chat_completion(
                messages=[{"role": "user", "content": "Say 'OK' in one word."}],
                max_tokens=10,
            )
            return {"status": "connected", "response": response.strip()}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def _parse_json(content: str) -> dict:
        """Parse JSON from LLM output, handling markdown code blocks."""
        content = content.strip()
        # Strip markdown code block wrapper
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (```json and ```)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON output: %s", str(e))
            logger.debug("Raw content: %s", content[:500])
            raise ValueError(f"LLM returned invalid JSON: {e}")


# Global singleton
llm_client = LLMClient()

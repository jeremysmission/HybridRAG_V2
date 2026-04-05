"""
Unified LLM client — wraps openai SDK v1.x for GPT-4o / GPT-OSS-120B.

Online-only. No offline mode. No Ollama.
Pinned to openai SDK v1.x — NEVER upgrade to 2.x.

Supports:
  - Azure OpenAI (primary)
  - AI Toolbox GPT-OSS endpoints (free tier)
  - Streaming and non-streaming responses
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import AzureOpenAI


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient:
    """
    Unified LLM client for HybridRAG V2.

    Uses openai SDK v1.x AzureOpenAI client.
    Reads API key from environment or Windows Credential Manager.
    """

    def __init__(
        self,
        api_base: str = "",
        api_version: str = "2024-10-21",
        model: str = "gpt-4o",
        deployment: str = "gpt-4o",
        max_tokens: int = 16384,
        temperature: float = 0.08,
        timeout_seconds: int = 180,
    ):
        self.model = model
        self.deployment = deployment
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Resolve API key from env
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            # Try keyring (Windows Credential Manager)
            try:
                import keyring
                api_key = keyring.get_password("hybridrag-v2", "azure-openai") or ""
            except Exception:
                pass

        resolved_base = api_base or os.getenv("AZURE_OPENAI_ENDPOINT", "")

        if resolved_base and api_key:
            self._client = AzureOpenAI(
                azure_endpoint=resolved_base,
                api_key=api_key,
                api_version=api_version,
                timeout=timeout_seconds,
            )
            self._available = True
        else:
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        """Whether the LLM client has valid credentials configured."""
        return self._available

    def call(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Make a single LLM call. Returns LLMResponse.

        Raises RuntimeError if client is not configured.
        """
        if not self._available:
            raise RuntimeError(
                "LLM client not configured. Set AZURE_OPENAI_ENDPOINT and "
                "AZURE_OPENAI_API_KEY environment variables, or configure "
                "api_base in config.yaml."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            text=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

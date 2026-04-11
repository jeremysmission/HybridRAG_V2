"""
Unified LLM client — wraps openai SDK v1.x for GPT-4o / GPT-OSS-120B.

Supports:
  - Azure OpenAI (work/production — api-key auth)
  - Commercial OpenAI (dev/home — Bearer auth)
  - Ollama phi4 (free offline — stress tests, no API cost)
  - Provider auto-detection from URL patterns

Online-only for generation. Ollama path is opt-in for testing.
Pinned to openai SDK v1.x — NEVER upgrade to 2.x.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from openai import AzureOpenAI, OpenAI

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int


def _detect_provider(endpoint: str) -> str:
    """
    Auto-detect provider from endpoint URL.

    Azure patterns: 'azure', 'cognitiveservices', '/openai/deployments/'
    OpenAI patterns: 'api.openai.com' or empty (uses SDK default)
    Ollama patterns: 'ollama' or loopback-host OpenAI-compatible URLs
    """
    if not endpoint:
        return "openai"

    lower = endpoint.lower()
    if any(p in lower for p in ["azure", "cognitiveservices", "/openai/deployments/", "aoai"]):
        return "azure"
    if any(p in lower for p in ["localhost", "127.0.0.1", "0.0.0.0", "11434", "ollama"]):
        return "ollama"
    return "openai"


class LLMClient:
    """
    Unified LLM client for HybridRAG V2.

    Provider resolution order:
      1. Explicit provider_override parameter
      2. HYBRIDRAG_API_PROVIDER env var
      3. Auto-detect from endpoint URL
      4. Default to "openai" if key present without endpoint

    Credential resolution order:
      1. Constructor parameters (api_base, api_key)
      2. Environment variables (multiple aliases supported)
      3. Windows Credential Manager (keyring)
    """

    # Env var aliases (checked in order, first match wins)
    _KEY_VARS = ["HYBRIDRAG_API_KEY", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"]
    _ENDPOINT_VARS = [
        "HYBRIDRAG_API_ENDPOINT", "AZURE_OPENAI_ENDPOINT",
        "OPENAI_API_ENDPOINT", "OPENAI_BASE_URL",
    ]
    _KEYRING_KEY_CANDIDATES = [
        ("hybridrag-v2", "azure-openai"),
        ("hybridrag", "azure_api_key"),
        ("azure_api_key@hybridrag", "azure_api_key"),
    ]
    _KEYRING_ENDPOINT_CANDIDATES = [
        ("hybridrag", "azure_endpoint"),
        ("azure_endpoint@hybridrag", "azure_endpoint"),
    ]

    def __init__(
        self,
        api_base: str = "",
        api_version: str = "2024-10-21",
        model: str = "gpt-4o",
        deployment: str = "gpt-4o",
        max_tokens: int = 16384,
        temperature: float = 0.08,
        timeout_seconds: int = 180,
        provider_override: str = "",
    ):
        self.model = model
        self.deployment = deployment
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Resolve credentials
        api_key = self._resolve_key()
        resolved_base = self._resolve_endpoint(api_base)
        provider = provider_override or os.getenv("HYBRIDRAG_API_PROVIDER", "")

        if not provider:
            provider = _detect_provider(resolved_base)

        self._provider = provider
        self._client = None
        self._available = False

        if not api_key and provider != "ollama":
            logger.warning("No API key found -- LLM client unavailable")
            return

        try:
            if provider == "azure":
                if not resolved_base:
                    logger.warning("Azure provider requires endpoint — LLM unavailable")
                    return
                self._client = AzureOpenAI(
                    azure_endpoint=resolved_base,
                    api_key=api_key,
                    api_version=api_version,
                    timeout=timeout_seconds,
                )
                self._available = True
                logger.info("LLM client ready: Azure OpenAI (%s)", deployment)

            elif provider == "openai":
                kwargs = {"api_key": api_key, "timeout": timeout_seconds}
                if resolved_base:
                    kwargs["base_url"] = resolved_base
                self._client = OpenAI(**kwargs)
                self._available = True
                logger.info("LLM client ready: OpenAI (%s)", model)

            elif provider == "ollama":
                # Ollama exposes an OpenAI-compatible API
                base = resolved_base or "http://localhost:11434/v1"
                self._client = OpenAI(
                    base_url=base,
                    api_key="ollama",  # Ollama ignores API key but SDK requires one
                    timeout=timeout_seconds,
                )
                self._available = True
                logger.info("LLM client ready: Ollama (%s)", model)

            else:
                logger.error("Unknown provider: %s", provider)

        except Exception as e:
            logger.error("LLM client init failed: %s", e)
            self._client = None
            self._available = False

    def _resolve_key(self) -> str:
        """Resolve API key from env vars or keyring."""
        for var in self._KEY_VARS:
            val = os.getenv(var, "")
            if val:
                return val

        # Keyring fallback
        try:
            import keyring
            for service, username in self._KEYRING_KEY_CANDIDATES:
                val = keyring.get_password(service, username) or ""
                if val:
                    logger.info(
                        "LLM client key resolved from Windows Credential Manager: %s/%s",
                        service, username,
                    )
                    return val
        except Exception:
            pass

        return ""

    def _resolve_endpoint(self, explicit: str) -> str:
        """Resolve endpoint from explicit param or env vars."""
        if explicit:
            return explicit
        for var in self._ENDPOINT_VARS:
            val = os.getenv(var, "")
            if val:
                return val
        try:
            import keyring
            for service, username in self._KEYRING_ENDPOINT_CANDIDATES:
                val = keyring.get_password(service, username) or ""
                if val:
                    logger.info(
                        "LLM client endpoint resolved from Windows Credential Manager: %s/%s",
                        service, username,
                    )
                    return val
        except Exception:
            pass
        return ""

    @property
    def available(self) -> bool:
        """Whether the LLM client has valid credentials configured."""
        return self._available

    @property
    def provider(self) -> str:
        """Active provider: 'azure', 'openai', or 'ollama'."""
        return self._provider

    def call(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """
        Make a single LLM call. Returns LLMResponse.

        Raises RuntimeError if client is not configured.
        Handles Azure vs OpenAI parameter differences automatically.
        """
        if not self._available:
            raise RuntimeError(
                "LLM client not configured. Set OPENAI_API_KEY (commercial) or "
                "AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY (Azure)."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build kwargs — model param differs between Azure (deployment) and OpenAI (model)
        kwargs = {
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if self._provider == "azure":
            kwargs["model"] = self.deployment
        else:
            kwargs["model"] = self.model

        if response_format:
            kwargs["response_format"] = response_format

        # Try with max_tokens first, fall back to max_completion_tokens
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            if "max_tokens" in str(e) and "max_completion_tokens" in str(e):
                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                response = self._client.chat.completions.create(**kwargs)
            else:
                raise

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            text=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

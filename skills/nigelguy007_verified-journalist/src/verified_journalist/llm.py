"""Provider-agnostic LLM access with usage accounting and validated JSON output."""

from __future__ import annotations

import json
import re
import threading
from collections import defaultdict
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .config import Settings

Tier = Literal["smart", "fast"]
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def complete(
        self, system: str, prompt: str, *, tier: Tier = "smart", max_tokens: int = 4096
    ) -> str: ...

    def usage(self) -> dict: ...


class _UsageMixin:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usage: dict[str, dict[str, int]] = defaultdict(
            lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        )

    def _record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            row = self._usage[model]
            row["calls"] += 1
            row["input_tokens"] += input_tokens or 0
            row["output_tokens"] += output_tokens or 0

    def usage(self) -> dict:
        with self._lock:
            return {model: dict(row) for model, row in self._usage.items()}


class AnthropicLLM(_UsageMixin):
    def __init__(self, api_key: str, smart_model: str, fast_model: str) -> None:
        super().__init__()
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key, max_retries=4, timeout=180)
        self._models = {"smart": smart_model, "fast": fast_model}

    def complete(self, system, prompt, *, tier="smart", max_tokens=4096):
        model = self._models[tier]
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        self._record(model, resp.usage.input_tokens, resp.usage.output_tokens)
        text = "".join(block.text for block in resp.content if block.type == "text")
        if resp.stop_reason == "max_tokens":
            raise LLMError(f"{model} hit max_tokens={max_tokens}; output was truncated")
        return text


class OpenAILLM(_UsageMixin):
    def __init__(self, api_key: str, smart_model: str, fast_model: str) -> None:
        super().__init__()
        import openai

        self._client = openai.OpenAI(api_key=api_key, max_retries=4, timeout=180)
        self._models = {"smart": smart_model, "fast": fast_model}

    def complete(self, system, prompt, *, tier="smart", max_tokens=4096):
        model = self._models[tier]
        resp = self._client.chat.completions.create(
            model=model,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        if resp.usage:
            self._record(model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            raise LLMError(f"{model} hit max_tokens={max_tokens}; output was truncated")
        return choice.message.content or ""


def make_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicLLM(settings.anthropic_api_key, settings.smart_model, settings.fast_model)
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAILLM(settings.openai_api_key, settings.smart_model, settings.fast_model)
    raise LLMError("No usable LLM configured: set ANTHROPIC_API_KEY or OPENAI_API_KEY")


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _extract_json(text: str) -> str:
    text = _FENCE.sub("", text.strip())
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("no JSON object in response")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    if end < start:
        raise ValueError("unterminated JSON in response")
    return text[start : end + 1]


def complete_json(
    llm: LLM,
    system: str,
    prompt: str,
    schema: type[T],
    *,
    tier: Tier = "fast",
    max_tokens: int = 4096,
    retries: int = 2,
) -> T:
    """Ask for JSON matching `schema`, validate it, and feed errors back on failure."""
    schema_json = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    full_system = (
        f"{system}\n\nRespond with a single JSON object that validates against this JSON "
        f"Schema, and nothing else (no prose, no code fences):\n{schema_json}"
    )
    attempt_prompt = prompt
    last_error: Exception | None = None
    for _ in range(retries + 1):
        raw = llm.complete(full_system, attempt_prompt, tier=tier, max_tokens=max_tokens)
        try:
            return schema.model_validate_json(_extract_json(raw))
        except (ValueError, ValidationError) as exc:
            last_error = exc
            attempt_prompt = (
                f"{prompt}\n\nYour previous reply was not valid. Error:\n{str(exc)[:1500]}\n"
                "Reply again with only the corrected JSON object."
            )
    raise LLMError(f"Model did not return valid {schema.__name__}: {last_error}")

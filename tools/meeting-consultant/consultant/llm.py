"""Claude wrapper: plain text, JSON, optional server-side web search, prompt caching."""
import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

import anthropic

from .config import Settings


def parse_json(text: str) -> Any:
    """Read a JSON value tolerantly: whole reply, a fenced block, or first {...} span."""
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1))
        except ValueError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("No JSON object in model reply")


class LLM:
    def __init__(self, settings: Settings, client: Optional[anthropic.AsyncAnthropic] = None):
        self.settings = settings
        self.client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key or "missing-key")  # start anyway; calls fail until a key is set

    async def text(
        self,
        purpose: str,
        model: str,
        prompt: Union[str, List[Dict[str, Any]]],
        system: Optional[str] = None,
        cached_system: Optional[str] = None,
        max_tokens: int = 1500,
        web_search: bool = False,
    ) -> str:
        """`purpose` labels the call for logs and tests. `cached_system` is the large,
        stable part of the system prompt (persona + loaded skills) and is cache-marked."""
        messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else list(prompt)
        kwargs: Dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
        blocks = []
        if cached_system:
            blocks.append({"type": "text", "text": cached_system, "cache_control": {"type": "ephemeral"}})
        if system:
            blocks.append({"type": "text", "text": system})
        if blocks:
            kwargs["system"] = blocks
        if web_search and self.settings.web_search:
            kwargs["tools"] = [{"type": self.settings.web_search_tool, "name": "web_search", "max_uses": 3}]

        for _ in range(4):  # server tools can pause a long turn; continue it
            resp = await self.client.messages.create(**kwargs)
            if resp.stop_reason != "pause_turn":
                break
            kwargs["messages"] = kwargs["messages"] + [{"role": "assistant", "content": resp.content}]
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()

    async def json(self, purpose: str, model: str, prompt: str, system: Optional[str] = None,
                   cached_system: Optional[str] = None, max_tokens: int = 3000) -> Dict[str, Any]:
        out = await self.text(purpose, model, prompt, system=system, cached_system=cached_system,
                              max_tokens=max_tokens)
        value = parse_json(out)
        if not isinstance(value, dict):
            raise ValueError(f"{purpose}: expected a JSON object")
        return value

    async def agent(
        self,
        purpose: str,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        handlers: Dict[str, Callable[..., Awaitable[Any]]],
        cached_system: Optional[str] = None,
        max_tokens: int = 1500,
        web_search: bool = True,
        max_rounds: int = 6,
    ) -> str:
        """Tool-use loop: Claude may search the web (server tool) and call our local tools
        (start research agents, join a meeting, ...). Returns the final text."""
        kwargs: Dict[str, Any] = {"model": model, "max_tokens": max_tokens}
        if cached_system:
            kwargs["system"] = [{"type": "text", "text": cached_system, "cache_control": {"type": "ephemeral"}}]
        all_tools = list(tools)
        if web_search and self.settings.web_search:
            all_tools.insert(0, {"type": self.settings.web_search_tool, "name": "web_search", "max_uses": 3})
        if all_tools:
            kwargs["tools"] = all_tools
        msgs = list(messages)
        resp = None
        for _ in range(max_rounds):
            resp = await self.client.messages.create(messages=list(msgs), **kwargs)
            msgs.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "pause_turn":
                continue
            if resp.stop_reason != "tool_use":
                break
            results = []
            for block in resp.content:
                if getattr(block, "type", "") != "tool_use":
                    continue
                handler = handlers.get(block.name)
                try:
                    out = await handler(**(block.input or {})) if handler else f"Unknown tool {block.name}"
                except Exception as e:  # noqa: BLE001 — report tool errors back to Claude
                    out = f"Error: {e}"
                content = out if isinstance(out, str) else json.dumps(out, default=str)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content[:20000]})
            msgs.append({"role": "user", "content": results})
        if resp is None:
            return ""
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()

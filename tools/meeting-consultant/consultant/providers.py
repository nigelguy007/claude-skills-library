"""Second opinions from other AI services. Each one is used only when its key is set."""
import asyncio
from typing import Any, Dict, List, Optional

import httpx

from .config import Settings
from .llm import LLM


class Providers:
    def __init__(self, settings: Settings, llm: LLM, http: Optional[httpx.AsyncClient] = None):
        self.s = settings
        self.llm = llm
        self.http = http or httpx.AsyncClient(timeout=90)

    def available(self) -> List[str]:
        names = ["claude"]
        if self.s.openai_api_key:
            names.append("chatgpt")
        if self.s.perplexity_api_key:
            names.append("perplexity")
        if self.s.custom_llm_url and self.s.custom_llm_model:
            names.append((self.s.custom_llm_name or "custom").lower())
        return names

    async def ask(self, name: str, question: str) -> Dict[str, Any]:
        try:
            if name == "claude":
                text = await self.llm.text("provider_claude", self.s.live_model, question, web_search=True,
                                           max_tokens=1500)
                return {"answer": text, "sources": []}
            if name == "chatgpt":
                return await self._openai_compatible("https://api.openai.com/v1/chat/completions",
                                                     self.s.openai_api_key, self.s.openai_model, question)
            if name == "perplexity":
                return await self._openai_compatible("https://api.perplexity.ai/chat/completions",
                                                     self.s.perplexity_api_key, self.s.perplexity_model, question)
            if name == (self.s.custom_llm_name or "custom").lower():
                url = self.s.custom_llm_url.rstrip("/")
                url = url if url.endswith("/chat/completions") else f"{url}/chat/completions"
                return await self._openai_compatible(url, self.s.custom_llm_key, self.s.custom_llm_model, question)
            return {"error": f"{name} is not configured"}
        except Exception as e:  # noqa: BLE001 — one failing provider must not sink the others
            return {"error": f"{type(e).__name__}: {e}"[:300]}

    async def _openai_compatible(self, url: str, key: Optional[str], model: str, question: str) -> Dict[str, Any]:
        resp = await self.http.post(url, headers={"Authorization": f"Bearer {key}"},
                                    json={"model": model, "messages": [{"role": "user", "content": question}]})
        resp.raise_for_status()
        data = resp.json()
        sources = data.get("citations") or [r.get("url") for r in data.get("search_results") or [] if r.get("url")]
        return {"answer": data["choices"][0]["message"]["content"], "sources": sources[:10]}

    async def ask_all(self, question: str, names: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        names = [n for n in (names or self.available()) if n in self.available()]
        results = await asyncio.gather(*(self.ask(n, question) for n in names))
        return dict(zip(names, results))

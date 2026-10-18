"""Thin async client for the Recall.ai meeting-bot API (v1.11 recording_config style)."""
import asyncio
import base64
from typing import Any, Dict, List, Optional

import httpx

from .config import PKG_DIR

SILENT_MP3_B64 = base64.b64encode((PKG_DIR / "assets" / "silence.mp3").read_bytes()).decode()

REALTIME_EVENTS = [
    "transcript.data",
    "participant_events.chat_message",
    "participant_events.join",
    "participant_events.leave",
]


def chat_limit(meeting_url: str) -> int:
    """Per-platform chat message length limits documented by Recall."""
    return 480 if "meet.google.com" in (meeting_url or "") else 4000


def chunk_message(text: str, limit: int) -> List[str]:
    """Split on paragraph, then sentence, then word boundaries so each piece fits."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    pieces: List[str] = []
    current = ""
    for unit in _units(text, limit):
        candidate = f"{current}\n{unit}" if current else unit
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = unit
    if current:
        pieces.append(current)
    return pieces


def _units(text: str, limit: int) -> List[str]:
    out: List[str] = []
    for para in text.split("\n"):
        if len(para) <= limit:
            out.append(para)
            continue
        sentences = para.replace("? ", "?\u0000").replace(". ", ".\u0000").replace("! ", "!\u0000").split("\u0000")
        for s in sentences:
            while len(s) > limit:
                cut = s.rfind(" ", 0, limit)
                cut = cut if cut > 0 else limit
                out.append(s[:cut])
                s = s[cut:].lstrip()
            if s:
                out.append(s)
    return [u for u in out if u.strip()]


class RecallClient:
    def __init__(self, api_key: str, region: str, http: Optional[httpx.AsyncClient] = None):
        self.base = f"https://{region}.recall.ai/api/v1"
        self.http = http or httpx.AsyncClient(
            timeout=30,
            headers={"Authorization": api_key or "", "accept": "application/json"},
        )

    async def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self.http.post(f"{self.base}{path}", json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"Recall {path} failed ({resp.status_code}): {resp.text[:500]}")
        return resp.json() if resp.content else {}

    async def create_bot(
        self,
        meeting_url: str,
        bot_name: str,
        webhook_url: str,
        join_message: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        body = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "metadata": metadata or {},
            "recording_config": {
                "transcript": {
                    "provider": {
                        # Low-latency mode returns utterances in ~1-3 s (English only).
                        "recallai_streaming": {"mode": "prioritize_low_latency", "language_code": "en"}
                    },
                    "diarization": {"use_separate_streams_when_available": True},
                },
                "participant_events": {},
                "realtime_endpoints": [
                    {"type": "webhook", "url": webhook_url, "events": REALTIME_EVENTS}
                ],
            },
            "chat": {"on_bot_join": {"send_to": "everyone", "message": join_message, "pin": True}},
            # The Output Audio endpoint only works when automatic_audio_output is configured,
            # so give it a half-second of silence.
            "automatic_audio_output": {"in_call_recording": {"data": {"kind": "mp3", "b64_data": SILENT_MP3_B64}}},
        }
        return await self._post("/bot/", body)

    async def send_chat(self, bot_id: str, message: str, meeting_url: str = "") -> None:
        for piece in chunk_message(message, chat_limit(meeting_url)):
            await self._post(f"/bot/{bot_id}/send_chat_message/", {"message": piece})
            await asyncio.sleep(0.3)  # keep multi-part messages in order

    async def output_audio(self, bot_id: str, mp3: bytes) -> None:
        await self._post(f"/bot/{bot_id}/output_audio/", {"kind": "mp3", "b64_data": base64.b64encode(mp3).decode()})

    async def leave(self, bot_id: str) -> None:
        await self._post(f"/bot/{bot_id}/leave_call/", {})

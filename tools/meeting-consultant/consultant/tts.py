"""Optional text-to-speech so the bot can say short questions out loud."""
from typing import Optional

import httpx

from .config import Settings


class TTS:
    def __init__(self, settings: Settings, http: Optional[httpx.AsyncClient] = None):
        self.s = settings
        self.http = http or httpx.AsyncClient(timeout=30)

    @property
    def available(self) -> bool:
        if self.s.tts_provider == "openai":
            return bool(self.s.openai_api_key)
        if self.s.tts_provider == "elevenlabs":
            return bool(self.s.elevenlabs_api_key and self.s.elevenlabs_voice_id)
        return False

    async def synth(self, text: str) -> Optional[bytes]:
        if not self.available or not text.strip():
            return None
        if self.s.tts_provider == "openai":
            resp = await self.http.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {self.s.openai_api_key}"},
                json={"model": self.s.openai_tts_model, "voice": self.s.openai_tts_voice,
                      "input": text, "response_format": "mp3"},
            )
        else:
            resp = await self.http.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.s.elevenlabs_voice_id}",
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": self.s.elevenlabs_api_key},
                json={"text": text, "model_id": self.s.elevenlabs_model},
            )
        resp.raise_for_status()
        return resp.content

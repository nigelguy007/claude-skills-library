"""Runtime settings, read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

PKG_DIR = Path(__file__).resolve().parent
TOOL_DIR = PKG_DIR.parent
REPO_ROOT = TOOL_DIR.parent.parent


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(_env(name, str(default)))


def _bool(name: str, default: bool) -> bool:
    value = _env(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str) -> List[str]:
    return [p.strip() for p in _env(name, default).split(",") if p.strip()]


@dataclass
class Settings:
    # Credentials
    anthropic_api_key: Optional[str] = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    recall_api_key: Optional[str] = field(default_factory=lambda: _env("RECALL_API_KEY"))
    recall_region: str = field(default_factory=lambda: _env("RECALL_REGION", "us-east-1"))

    # Where Recall can reach this server, and the shared secrets that guard it
    # Render sets RENDER_EXTERNAL_URL automatically, so on Render this needs no setting.
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL")
                                 or _env("RENDER_EXTERNAL_URL", "http://localhost:8000"))
    webhook_token: str = field(default_factory=lambda: _env("WEBHOOK_TOKEN", "change-me"))
    admin_token: Optional[str] = field(default_factory=lambda: _env("ADMIN_TOKEN"))

    # Identity in the meeting. Pick a name that speech recognition hears reliably.
    bot_name: str = field(default_factory=lambda: _env("BOT_NAME", "Atlas (AI consultant)"))
    wake_words: List[str] = field(default_factory=lambda: _list("WAKE_WORDS", "atlas"))

    # Models
    live_model: str = field(default_factory=lambda: _env("LIVE_MODEL", "claude-sonnet-5-5"))
    deep_model: str = field(default_factory=lambda: _env("DEEP_MODEL", "claude-opus-5-5"))
    fast_model: str = field(default_factory=lambda: _env("FAST_MODEL", "claude-haiku-5-5"))
    web_search: bool = field(default_factory=lambda: _bool("WEB_SEARCH", True))
    web_search_tool: str = field(default_factory=lambda: _env("WEB_SEARCH_TOOL", "web_search_20250305"))

    # Participation policy
    default_mode: str = field(default_factory=lambda: _env("DEFAULT_MODE", "chat"))  # chat | voice
    analysis_interval_s: float = field(default_factory=lambda: _float("ANALYSIS_INTERVAL_S", 90))
    min_new_chars: int = field(default_factory=lambda: _int("MIN_NEW_CHARS", 300))
    proactive_threshold: int = field(default_factory=lambda: _int("PROACTIVE_THRESHOLD", 8))
    proactive_min_gap_s: float = field(default_factory=lambda: _float("PROACTIVE_MIN_GAP_S", 240))
    max_proactive: int = field(default_factory=lambda: _int("MAX_PROACTIVE", 12))
    address_pause_s: float = field(default_factory=lambda: _float("ADDRESS_PAUSE_S", 2.5))
    address_max_wait_s: float = field(default_factory=lambda: _float("ADDRESS_MAX_WAIT_S", 10))
    voice_silence_s: float = field(default_factory=lambda: _float("VOICE_SILENCE_S", 3))
    skill_refresh_s: float = field(default_factory=lambda: _float("SKILL_REFRESH_S", 900))
    max_skills: int = field(default_factory=lambda: _int("MAX_SKILLS", 4))
    status_poll_s: float = field(default_factory=lambda: _float("STATUS_POLL_S", 60))
    inactivity_finish_s: float = field(default_factory=lambda: _float("INACTIVITY_FINISH_S", 900))

    # Voice (optional)
    tts_provider: str = field(default_factory=lambda: _env("TTS_PROVIDER", "none"))  # none | openai | elevenlabs
    openai_api_key: Optional[str] = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_tts_model: str = field(default_factory=lambda: _env("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"))
    openai_tts_voice: str = field(default_factory=lambda: _env("OPENAI_TTS_VOICE", "alloy"))
    elevenlabs_api_key: Optional[str] = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))
    elevenlabs_voice_id: Optional[str] = field(default_factory=lambda: _env("ELEVENLABS_VOICE_ID"))
    elevenlabs_model: str = field(default_factory=lambda: _env("ELEVENLABS_MODEL", "eleven_turbo_v2_5"))

    # Research agents and second opinions from other AI services (all optional)
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o"))
    perplexity_api_key: Optional[str] = field(default_factory=lambda: _env("PERPLEXITY_API_KEY"))
    perplexity_model: str = field(default_factory=lambda: _env("PERPLEXITY_MODEL", "sonar-pro"))
    # Any OpenAI-compatible chat API (e.g. a Genspark or OpenRouter endpoint, if you have one)
    custom_llm_name: Optional[str] = field(default_factory=lambda: _env("CUSTOM_LLM_NAME"))
    custom_llm_url: Optional[str] = field(default_factory=lambda: _env("CUSTOM_LLM_URL"))
    custom_llm_key: Optional[str] = field(default_factory=lambda: _env("CUSTOM_LLM_KEY"))
    custom_llm_model: Optional[str] = field(default_factory=lambda: _env("CUSTOM_LLM_MODEL"))
    cross_check: bool = field(default_factory=lambda: _bool("CROSS_CHECK", True))
    max_sub_agents: int = field(default_factory=lambda: _int("MAX_SUB_AGENTS", 4))
    max_auto_research: int = field(default_factory=lambda: _int("MAX_AUTO_RESEARCH", 6))
    # Where to send notes after a meeting (Slack-compatible incoming webhook)
    notify_webhook_url: Optional[str] = field(default_factory=lambda: _env("NOTIFY_WEBHOOK_URL"))

    # Storage
    # Comma-separated. Add ~/.claude/skills or any other skill collection here.
    skills_dirs: List[str] = field(default_factory=lambda: _list("SKILLS_DIRS", str(REPO_ROOT / "skills")))
    learned_skills_dir: str = field(default_factory=lambda: _env("LEARNED_SKILLS_DIR", str(TOOL_DIR / "learned_skills")))
    data_dir: str = field(default_factory=lambda: _env("DATA_DIR", str(TOOL_DIR / "data")))

    @property
    def realtime_webhook_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}/webhook/recall/realtime?token={self.webhook_token}"

    @property
    def status_webhook_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}/webhook/recall/status?token={self.webhook_token}"

    @property
    def short_name(self) -> str:
        return self.bot_name.split("(")[0].strip() or self.bot_name

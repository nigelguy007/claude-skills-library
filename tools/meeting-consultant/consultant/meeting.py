"""Per-meeting state, persisted as JSON so a restart doesn't lose a live meeting."""
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _fmt(t: float) -> str:
    s = int(max(t, 0))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


@dataclass
class Meeting:
    id: str
    meeting_url: str
    topic: str = ""
    context: str = ""
    mode: str = "chat"  # chat | voice
    status: str = "joining"  # joining | live | finishing | done | failed
    created_at: float = field(default_factory=time.time)
    utterances: List[Dict[str, Any]] = field(default_factory=list)  # {speaker, text, t, wall}
    chat: List[Dict[str, Any]] = field(default_factory=list)  # {speaker, text, wall, from_bot}
    participants: Dict[str, str] = field(default_factory=dict)
    brief: Optional[Dict[str, Any]] = None
    profile: Optional[Dict[str, Any]] = None  # {domain, expert_persona, keywords}
    hindsight_questions: List[str] = field(default_factory=list)
    skills: List[Dict[str, str]] = field(default_factory=list)  # {name, path, why, source}
    interventions: List[Dict[str, Any]] = field(default_factory=list)  # {wall, kind, text, value}
    exchanges: List[Dict[str, str]] = field(default_factory=list)  # {asker, q, a}
    quiet: bool = False
    posted_hindsight: bool = False
    last_analysis_wall: float = 0.0
    last_analysis_len: int = 0
    last_skill_pick_wall: float = 0.0
    last_proactive_wall: float = 0.0
    last_utterance_wall: float = 0.0
    pending_voice: Optional[Dict[str, Any]] = None
    report_path: Optional[str] = None
    learned_skill_path: Optional[str] = None
    notes_path: Optional[str] = None  # research + follow-ups, kept separate from the memo
    research_ids: List[str] = field(default_factory=list)
    error: Optional[str] = None

    # ---- transcript helpers ----
    def transcript_text(self, max_chars: int = 60000) -> str:
        lines = [f"[{_fmt(u['t'])}] {u['speaker']}: {u['text']}" for u in self.utterances]
        text = "\n".join(lines)
        return text if len(text) <= max_chars else "…\n" + text[-max_chars:]

    def recent(self, n: int = 25) -> str:
        return "\n".join(f"{u['speaker']}: {u['text']}" for u in self.utterances[-n:])

    def transcript_len(self) -> int:
        return sum(len(u["text"]) for u in self.utterances)

    def proactive_count(self) -> int:
        return sum(1 for i in self.interventions if i.get("kind") == "proactive")

    # ---- persistence ----
    def save(self, data_dir: str) -> None:
        d = Path(data_dir) / "meetings"
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"{self.id}.json.tmp"
        tmp.write_text(json.dumps(asdict(self)))
        tmp.replace(d / f"{self.id}.json")

    @classmethod
    def load_all(cls, data_dir: str) -> List["Meeting"]:
        d = Path(data_dir) / "meetings"
        out = []
        for p in sorted(d.glob("*.json")) if d.exists() else []:
            try:
                raw = json.loads(p.read_text())
                out.append(cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__}))
            except (ValueError, TypeError):
                continue
        return out

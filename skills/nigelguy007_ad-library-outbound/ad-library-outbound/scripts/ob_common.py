"""Shared helpers for the ad-library-outbound scripts. Standard library only."""
import csv
import io
import json
import os
import re
import sys
import tempfile
import unicodedata
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union
from urllib.parse import urlparse

PathLike = Union[str, Path]

PRIVATE_FILE_MODE = 0o600  # files here hold names and email addresses

_COMPANY_SUFFIXES = frozenset(
    "inc llc ltd limited corp corporation co company gmbh plc sa bv pty ag srl sas lp llp".split()
)
_FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'"})
_EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}")
_DOMAIN = re.compile(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def out(text: str) -> None:
    """Write one line of command output to stdout."""
    sys.stdout.write(text + "\n")


# ---------------------------------------------------------------- text

def normalize_name(name: Any) -> str:
    """Lowercase a company or person name and drop accents, punctuation and legal suffixes."""
    text = unicodedata.normalize("NFKD", "" if name is None else str(name))
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    words = re.sub(r"[^\w& ]+", " ", text).replace("_", " ").split()
    while words and words[-1] in _COMPANY_SUFFIXES:
        words = words[:-1]
    return " ".join(words)


def fold(text: Optional[str]) -> str:
    """Normalise quotes, whitespace and case so two spellings of one line compare equal."""
    return " ".join((text or "").translate(_QUOTES).split()).casefold()


def word_count(text: str) -> int:
    return len(text.split())


def numeric_tokens(text: Optional[str]) -> Set[str]:
    """Every number in the text, without thousands separators: '12,000' -> '12000'."""
    return {match.replace(",", "").rstrip(".") for match in _NUMBER.findall(text or "")}


def valid_id(value: Optional[str]) -> bool:
    """True for a short id that is safe to use in a file name (letters, digits, '.', '_', '-')."""
    return bool(value) and ".." not in value and bool(_ID.fullmatch(value))


# ---------------------------------------------------------------- addresses and domains

def bare_address(value: Optional[str]) -> str:
    """The value as one lowercased email address, or '' when it is anything else (a list, a name, junk)."""
    address = (value or "").strip().rstrip(".").lower()
    return address if _EMAIL.fullmatch(address) else ""


def normalize_address(value: Optional[str]) -> str:
    """The email address inside a value such as 'Jane Roe <Jane@X.com>' or 'mailto:j@x.com', or ''."""
    text = (value or "").strip()
    if text.lower().startswith("mailto:"):
        text = text[7:]
    return bare_address(parseaddr(text)[1])


def domain_of(value: Optional[str]) -> str:
    """The bare domain of an email address or URL, lowercased, without 'www.' or a trailing dot."""
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "@" in value and "://" not in value:
        host = value.rsplit("@", 1)[1]
    else:
        try:
            host = urlparse(value if "://" in value else "https://" + value).hostname or ""
        except ValueError:
            host = ""
    host = host.strip().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def is_domain(value: Optional[str]) -> bool:
    return bool(_DOMAIN.fullmatch(value or ""))


def domain_matches(domain: str, known: Iterable[str]) -> bool:
    """True when the domain is one of the known domains or a subdomain of one."""
    return bool(domain) and any(domain == item or domain.endswith("." + item) for item in known)


# ---------------------------------------------------------------- front matter

def _clean_value(value: str) -> str:
    value = value.strip()
    if value == "#" or value.startswith("# "):
        return ""
    if value[:1] in ("'", '"'):
        end = value.find(value[0], 1)
        if end != -1 and (end == len(value) - 1 or value[end + 1:].lstrip().startswith("#")):
            return value[1:end]
    return value


def parse_front_matter(text: str) -> Tuple[Dict[str, str], str]:
    """Split '---' front matter (flat 'key: value' lines) from the body. A repeated key is an error."""
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    meta: Dict[str, str] = {}
    for line in match.group(1).split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key in meta:
            raise ValueError("front matter has the key %r twice" % key)
        meta[key] = _clean_value(value)
    return meta, text[match.end():]


def set_front_matter(text: str, updates: Dict[str, str]) -> str:
    """Return the text with these front-matter keys set, replacing a key's line or adding it at the end."""
    match = _FRONT_MATTER.match(text)
    if not match:
        raise ValueError("the file has no front matter")
    if any("\n" in value or "\r" in value for value in updates.values()):
        raise ValueError("front-matter values must be a single line")
    remaining = dict(updates)
    lines: List[str] = []
    for line in match.group(1).split("\n"):
        stripped = line.strip()
        key = stripped.split(":", 1)[0].strip() if ":" in stripped and not stripped.startswith("#") else None
        if key in remaining:
            lines.append("%s: %s" % (key, remaining.pop(key)))
        else:
            lines.append(line.rstrip("\r"))
    lines.extend("%s: %s" % item for item in remaining.items())
    return "---\n" + "\n".join(lines) + "\n---\n" + text[match.end():]


def split_sections(body: str) -> Dict[str, str]:
    """Map each '## Heading' to the text under it, in document order."""
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in body.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


# ---------------------------------------------------------------- files

def atomic_write(path: PathLike, text: str) -> None:
    """Write a file in one step so a crash never leaves it half-written. The file is private (0600)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp-", suffix=target.suffix)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as temp:
            temp.write(text)
        os.replace(temp_name, str(target))
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def read_jsonl(path: PathLike) -> List[Dict[str, Any]]:
    """Read a JSON-lines file of objects. A missing file is an empty list."""
    source = Path(path)
    if not source.exists():
        return []
    rows: List[Dict[str, Any]] = []
    # split on "\n" only: ad text can hold U+2028 and friends, which str.splitlines() would break on
    for number, line in enumerate(source.read_text(encoding="utf-8").split("\n"), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as err:
            raise ValueError("%s line %d is not valid JSON: %s" % (source, number, err)) from err
        if not isinstance(row, dict):
            raise ValueError("%s line %d is not a JSON object" % (source, number))
        rows.append(row)
    return rows


def write_jsonl(path: PathLike, rows: Iterable[Dict[str, Any]]) -> None:
    atomic_write(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def safe_cell(value: Any) -> str:
    """A CSV cell that a spreadsheet or sending tool will not run as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip(" ").startswith(_FORMULA_START) else text


def read_csv(path: PathLike, required: Sequence[str] = ()) -> List[Dict[str, str]]:
    """Read a CSV with a header row; header names are matched in lowercase. A missing file is empty.

    A file that has content but lacks a required column is an error, never a silent empty list.
    """
    source = Path(path)
    if not source.exists():
        return []
    try:
        with source.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = [(name or "").strip().lower() for name in (reader.fieldnames or [])]
            rows = [{(key or "").strip().lower(): (value or "") for key, value in row.items() if key is not None}
                    for row in reader]
    except csv.Error as err:
        raise ValueError("%s could not be read as CSV: %s" % (source, err)) from err
    missing = [name for name in required if name not in headers]
    if missing and headers:
        raise ValueError("%s has no '%s' column. Its first line must be the header row."
                         % (source, "', '".join(missing)))
    return rows


def _csv_text(fields: Sequence[str], rows: Iterable[Dict[str, Any]], header: bool) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    if header:
        writer.writeheader()
    for row in rows:
        writer.writerow({field: safe_cell(row.get(field, "")) for field in fields})
    return buffer.getvalue()


def append_csv(path: PathLike, fields: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    """Append rows to a private CSV, writing the header first if the file is new."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    is_new = not target.exists() or target.stat().st_size == 0
    needs_newline = False
    if not is_new:
        with target.open("rb") as existing:
            existing.seek(-1, os.SEEK_END)
            needs_newline = existing.read(1) not in (b"\n", b"\r")
    descriptor = os.open(str(target), os.O_WRONLY | os.O_APPEND | os.O_CREAT, PRIVATE_FILE_MODE)
    with os.fdopen(descriptor, "a", encoding="utf-8", newline="") as handle:
        handle.write(("\n" if needs_newline else "") + _csv_text(fields, rows, header=is_new))


def write_csv(path: PathLike, fields: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    """Replace a CSV with the given rows, in one step."""
    atomic_write(path, _csv_text(fields, rows, header=True))

"""
Agentic rekordbox classifier for fresh tracks.

This is not a one-shot tag filler. It collects local rekordbox context, gathers
web evidence, classifies the role of a track in a DJ set, and writes a reviewable
report. Writing to rekordbox is intentionally gated behind --apply.

Internet sources used without API keys:
- MusicBrainz recording search
- iTunes Search API

Optional:
- Discogs if DISCOGS_TOKEN is set
- OpenAI-compatible LLM review if OPENAI_API_KEY is set
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = PROJECT_DIR.parents[1] if PROJECT_DIR.parent.name.lower() == "outputs" else PROJECT_DIR.parent
for vendor_dir in (
    PROJECT_DIR / "work" / "pyrekordbox_vendor",
    PROJECT_DIR.parent / "work" / "pyrekordbox_vendor",
    WORKSPACE_DIR / "work" / "pyrekordbox_vendor",
):
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))
        break

from pyrekordbox.db6 import (  # noqa: E402
    DjmdArtist,
    DjmdColor,
    DjmdContent,
    DjmdGenre,
    DjmdKey,
    DjmdLabel,
    DjmdMyTag,
    DjmdSongMyTag,
    Rekordbox6Database,
)


DEFAULT_DB = Path(r"C:\Users\Admin\AppData\Roaming\Pioneer\rekordbox\master.db")
DEFAULT_RULES = Path(__file__).with_name("agent_rules.json")
CODEX_DECISION_SCHEMA = Path(__file__).with_name("codex_track_decision.schema.json")
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "reports"
BACKUP_ROOT = PROJECT_DIR / "backups"
USER_AGENT = "rekordbox-set-agent/0.1 (local library assistant)"


@dataclass
class TrackContext:
    content: Any
    artist: str
    genre: str
    label: str
    key: str
    color: str | None
    tags: set[str]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: Any) -> str:
    return str(value or "").strip()


def lower_blob(*values: Any) -> str:
    return " ".join(norm(value).lower() for value in values if value is not None)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_dt(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text[:26], fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    return None


def http_json(url: str, timeout: int = 12) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def bpm_value(content: Any) -> float:
    try:
        return float(content.BPM or 0) / 100.0
    except Exception:
        return 0.0


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    title = re.sub(r"\s*\[(official|visualizer|audio|video|extended)\]\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*[-_]\s*(beatport|promo|clean|dirty|www\..+)\s*$", "", title, flags=re.I)
    return title.strip()


def remove_mix_suffix(title: str) -> str:
    return re.sub(r"\s*\((extended|original|club|radio|dub|instrumental).*?mix\)\s*$", "", title, flags=re.I).strip()


class WebEvidenceCollector:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.cache: dict[str, Any] = {}

    def collect(self, artist: str, title: str) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "sources": []}
        key = f"{artist}::{title}"
        if key in self.cache:
            return self.cache[key]

        evidence = {
            "enabled": True,
            "sources": [],
            "musicbrainz": self.musicbrainz(artist, title),
            "itunes": self.itunes(artist, title),
            "discogs": self.discogs(artist, title),
            "search_urls": {
                "beatport": "https://www.beatport.com/search?q=" + urllib.parse.quote(f"{artist} {title}"),
                "google": "https://www.google.com/search?q=" + urllib.parse.quote(f"{artist} {title} Beatport"),
            },
        }
        for source in ("musicbrainz", "itunes", "discogs"):
            if evidence[source].get("hit"):
                evidence["sources"].append(source)
        self.cache[key] = evidence
        # Be polite to public APIs.
        time.sleep(0.15)
        return evidence

    def musicbrainz(self, artist: str, title: str) -> dict[str, Any]:
        query = f'recording:"{remove_mix_suffix(title)}" AND artist:"{artist}"'
        url = "https://musicbrainz.org/ws/2/recording?" + urllib.parse.urlencode(
            {"query": query, "fmt": "json", "limit": 5}
        )
        try:
            data = http_json(url)
        except Exception as exc:
            return {"hit": False, "error": str(exc), "url": url}
        recordings = data.get("recordings", [])
        if not recordings:
            return {"hit": False, "url": url}
        best = recordings[0]
        release = (best.get("releases") or [{}])[0]
        return {
            "hit": True,
            "url": url,
            "title": best.get("title"),
            "score": best.get("score"),
            "artist_credit": " ".join(part.get("name", "") for part in best.get("artist-credit", []) if isinstance(part, dict)),
            "release": release.get("title"),
            "date": release.get("date"),
        }

    def itunes(self, artist: str, title: str) -> dict[str, Any]:
        term = f"{artist} {remove_mix_suffix(title)}"
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": term, "media": "music", "entity": "song", "limit": 5}
        )
        try:
            data = http_json(url)
        except Exception as exc:
            return {"hit": False, "error": str(exc), "url": url}
        results = data.get("results", [])
        if not results:
            return {"hit": False, "url": url}
        best = results[0]
        return {
            "hit": True,
            "url": url,
            "track": best.get("trackName"),
            "artist": best.get("artistName"),
            "collection": best.get("collectionName"),
            "genre": best.get("primaryGenreName"),
            "release_date": best.get("releaseDate"),
        }

    def discogs(self, artist: str, title: str) -> dict[str, Any]:
        token = os.environ.get("DISCOGS_TOKEN", "").strip()
        if not token:
            return {"hit": False, "skipped": "DISCOGS_TOKEN not set"}
        url = "https://api.discogs.com/database/search?" + urllib.parse.urlencode(
            {"q": f"{artist} {title}", "type": "release", "per_page": 5, "token": token}
        )
        try:
            data = http_json(url)
        except Exception as exc:
            return {"hit": False, "error": str(exc), "url": url}
        results = data.get("results", [])
        if not results:
            return {"hit": False, "url": url}
        best = results[0]
        return {
            "hit": True,
            "url": url,
            "title": best.get("title"),
            "year": best.get("year"),
            "genre": best.get("genre"),
            "style": best.get("style"),
            "label": best.get("label"),
        }


class LibraryIndex:
    def __init__(self, db: Rekordbox6Database):
        self.db = db
        self.artists = {item.ID: item.Name for item in db.query(DjmdArtist).all()}
        self.genres = {item.ID: item.Name for item in db.query(DjmdGenre).all()}
        self.labels = {item.ID: item.Name for item in db.query(DjmdLabel).all()}
        self.keys = {item.ID: item.ScaleName for item in db.query(DjmdKey).all()}
        self.colors = {item.ID: item.Commnt for item in db.query(DjmdColor).all()}
        self.color_ids = {item.Commnt: item.ID for item in db.query(DjmdColor).all()}
        self.tag_names = {item.ID: item.Name for item in db.query(DjmdMyTag).filter(DjmdMyTag.rb_local_deleted == 0).all()}
        self.tags_by_parent_name = {
            (item.ParentID, item.Name): item
            for item in db.query(DjmdMyTag).filter(DjmdMyTag.rb_local_deleted == 0).all()
        }
        self.views = self._load_views()

    def _load_views(self) -> list[TrackContext]:
        links_by_content: dict[str, set[str]] = {}
        for link in self.db.query(DjmdSongMyTag).all():
            if link.MyTagID in self.tag_names:
                links_by_content.setdefault(link.ContentID, set()).add(self.tag_names[link.MyTagID])

        return [
            TrackContext(
                content=content,
                artist=self.artists.get(content.ArtistID, ""),
                genre=self.genres.get(content.GenreID, ""),
                label=self.labels.get(content.LabelID, ""),
                key=self.keys.get(content.KeyID, ""),
                color=self.colors.get(content.ColorID),
                tags=links_by_content.get(content.ID, set()),
            )
            for content in self.db.query(DjmdContent).all()
            if not content.rb_local_deleted
        ]

    def candidates(self, days: int, limit: int) -> list[TrackContext]:
        cutoff = utc_now() - dt.timedelta(days=days) if days > 0 else None
        managed_tags = {"OPEN", "WARM", "JOURNEY", "MAIN", "PEAK", "CLOSE", "A", "B", "C"}
        rows = []
        for view in self.views:
            created = parse_dt(view.content.created_at) or parse_dt(view.content.DateCreated)
            fresh = bool(cutoff and created and created >= cutoff)
            untagged = not (view.tags & managed_tags)
            if fresh or untagged:
                rows.append(view)
        rows.sort(key=lambda view: str(view.content.created_at or ""), reverse=True)
        return rows[:limit] if limit else rows


class SetClassifier:
    def __init__(self, rules: dict[str, Any]):
        self.rules = rules

    def normalize_genre(self, view: TrackContext, evidence: dict[str, Any]) -> tuple[str, list[str]]:
        values = [view.genre, view.label, view.content.Title, view.artist]
        if evidence.get("itunes", {}).get("genre"):
            values.append(evidence["itunes"]["genre"])
        if evidence.get("discogs", {}).get("style"):
            values.extend(evidence["discogs"]["style"])
        blob = lower_blob(*values)
        for rule in self.rules["genre_normalization"]:
            if any(token in blob for token in rule["if_any"]):
                return rule["tag"], [f"genre rule matched: {', '.join(rule['if_any'])}"]
        return view.genre or "Unknown", ["fallback to current metadata genre"]

    def moods(self, view: TrackContext, genre_normalized: str, evidence: dict[str, Any]) -> tuple[list[str], list[str]]:
        blob = lower_blob(view.content.Title, view.artist, view.label, genre_normalized)
        scores = {mood: 0 for mood in self.rules["moods"]}
        keywords = {
            "Vocal": ["vocal", "feat.", "ft.", "female", "male", "voice"],
            "Deep": ["deep", "dub", "low", "night", "saudade"],
            "Emotional": ["love", "swear", "heart", "feel", "tears", "soul"],
            "Atmospheric": ["dream", "mirage", "space", "cloud", "ambient", "afterlife"],
            "Hypnotic": ["hypnotic", "ritual", "acid", "loop", "trance"],
            "Driving": ["drive", "driving", "run", "power", "edge", "catalyst", "destructure"],
            "Dark": ["dark", "shadow", "black", "noire"],
            "Euphoric": ["higher", "light", "heaven", "sun", "classic"],
        }
        for mood, words in keywords.items():
            scores[mood] += sum(2 for word in words if word in blob)
        genre_l = genre_normalized.lower()
        if "progressive" in genre_l:
            scores["Atmospheric"] += 2
            scores["Emotional"] += 1
        if "melodic techno" in genre_l or genre_l == "techno":
            scores["Driving"] += 2
            scores["Hypnotic"] += 1
        if "afro" in genre_l or "organic" in genre_l:
            scores["Deep"] += 1
            scores["Atmospheric"] += 1
        if "deep house" in genre_l or "minimal" in genre_l:
            scores["Deep"] += 2
            scores["Hypnotic"] += 1
        if "electronica" in genre_l or "ambient" in genre_l:
            scores["Atmospheric"] += 2
            scores["Deep"] += 1
        if "breaks" in genre_l:
            scores["Atmospheric"] += 1
            scores["Driving"] += 1
        if "indie dance" in genre_l:
            scores["Driving"] += 1
            scores["Hypnotic"] += 1
        if "future house" in genre_l:
            scores["Driving"] += 3
            scores["Euphoric"] += 1
        if "bass house" in genre_l:
            scores["Driving"] += 2
            scores["Hypnotic"] += 1

        ranked = [m for m, s in sorted(scores.items(), key=lambda item: (-item[1], item[0])) if s > 0]
        chosen = ranked[:2] or ["Atmospheric"]
        return chosen, [f"mood scores: {scores}"]

    def rating_role_color(self, view: TrackContext, genre_normalized: str, moods: list[str]) -> tuple[int, str, str, list[str]]:
        bpm = bpm_value(view.content)
        reasons = []
        rating = 3
        g = genre_normalized.lower()
        if any(token in g for token in ["hard techno", "psy-trance", "drum & bass", "future house"]):
            rating += 2
            reasons.append("high intensity genre")
        elif "techno" in g:
            rating += 1
            reasons.append("techno lane")
        elif any(token in g for token in ["indie dance", "breaks", "bass house"]):
            rating += 1
            reasons.append("club main-time lane")
        elif any(token in g for token in ["organic", "afro", "deep house", "minimal"]):
            rating -= 1
            reasons.append("warm/deep genre lane")
        elif "electronica" in g or "ambient" in g:
            rating -= 2
            reasons.append("electronica/intro lane")

        if "Driving" in moods:
            rating += 1
            reasons.append("driving mood")
        if "Deep" in moods:
            rating -= 1
            reasons.append("deep mood")
        if bpm >= 130:
            rating += 1
            reasons.append("fast BPM")
        elif bpm and bpm <= 118:
            rating -= 1
            reasons.append("low BPM")
        if any(token in g for token in ["indie dance", "breaks", "bass house"]) and rating > 4:
            rating = 4
            reasons.append("club lane capped at main-time unless reviewed as peak")
        calibration_blob = lower_blob(view.artist, view.label, view.content.Title, genre_normalized)
        for rule in self.rules.get("library_calibration", []):
            if any(token in calibration_blob for token in rule.get("if_any", [])):
                delta = int(rule.get("rating_delta", 0))
                if delta:
                    rating += delta
                if "max_rating" in rule:
                    rating = min(rating, int(rule["max_rating"]))
                reasons.append(rule.get("reason", "library calibration matched"))
        rating = max(1, min(5, rating))

        if rating <= 1:
            role = "OPEN"
        elif rating == 2:
            role = "WARM"
        elif rating == 3:
            role = "JOURNEY"
        elif rating == 4:
            role = "MAIN"
        else:
            role = "PEAK"

        color = "Purple"
        color_text = self.rules["colors"]
        if role == "PEAK":
            color = "Red"
        elif role == "MAIN":
            color = "Orange"
        elif role == "CLOSE":
            color = "Pink"
        elif any(token in genre_normalized for token in ["Indie Dance", "Bass House"]):
            color = "Orange"
        elif "Future House" in genre_normalized:
            color = "Red" if role == "PEAK" else "Orange"
        elif "Breaks" in genre_normalized and bpm >= 128:
            color = "Orange"
        elif "Afro" in genre_normalized or "Organic" in genre_normalized:
            color = "Green"
        elif "Breaks" in genre_normalized:
            color = "Aqua"
        elif "Deep House" in genre_normalized or "Minimal" in genre_normalized:
            color = "Blue"
        elif "Electronica" in genre_normalized or "Ambient" in genre_normalized:
            color = "Blue"
        elif any(m in moods for m in ["Deep", "Emotional"]):
            color = "Blue"
        elif role == "WARM":
            color = "Blue"
        reasons.append(f"color {color}: {color_text.get(color, '')}")
        return rating, role, color, reasons

    def priority(self, rating: int, role: str, best_similarity: float, confidence: float) -> str:
        if rating >= 5 and confidence >= 0.7:
            return "A"
        if role in {"MAIN", "PEAK"} and best_similarity >= 70:
            return "A"
        if rating >= 3:
            return "B"
        return "C"


def key_family(key: str) -> str:
    match = re.match(r"(\d+)([AB])", norm(key), flags=re.I)
    if match:
        return match.group(1)
    return norm(key).rstrip("mM#b")


def similar_tracks(target: TrackContext, predicted: dict[str, Any], library: list[TrackContext], limit: int) -> list[dict[str, Any]]:
    target_bpm = bpm_value(target.content)
    target_key = key_family(target.key)
    desired = set(predicted["moods"]) | {predicted["role"], predicted["genre_normalized"]}
    scored = []
    for other in library:
        if other.content.ID == target.content.ID:
            continue
        score = 0.0
        reasons = []
        other_bpm = bpm_value(other.content)
        if target_bpm and other_bpm:
            bpm_score = max(0.0, 25.0 - abs(target_bpm - other_bpm) * 3.0)
            score += bpm_score
            if bpm_score >= 18:
                reasons.append("close BPM")
        if predicted["genre_normalized"] in other.tags or predicted["genre_normalized"].lower() in other.genre.lower():
            score += 25
            reasons.append("same lane")
        overlap = desired & other.tags
        if overlap:
            score += min(30, 8 * len(overlap))
            reasons.append("tag overlap: " + ", ".join(sorted(overlap)[:4]))
        if target_key and target_key == key_family(other.key):
            score += 10
            reasons.append("compatible key family")
        if score > 0:
            scored.append(
                {
                    "score": round(score, 1),
                    "artist": other.artist,
                    "title": other.content.Title,
                    "bpm": round(other_bpm, 2) if other_bpm else None,
                    "key": other.key,
                    "reason": "; ".join(reasons),
                }
            )
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]


def confidence(evidence: dict[str, Any], similar: list[dict[str, Any]], reasons: list[str]) -> float:
    value = 0.45
    if evidence.get("musicbrainz", {}).get("hit"):
        value += 0.12
    if evidence.get("itunes", {}).get("hit"):
        value += 0.10
    if evidence.get("discogs", {}).get("hit"):
        value += 0.15
    if similar:
        value += min(0.20, similar[0]["score"] / 500.0)
    if reasons:
        value += 0.06
    return round(min(0.98, value), 2)


def optional_llm_review(enabled: bool, model: str, record: dict[str, Any]) -> dict[str, Any] | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not enabled or not api_key:
        return None
    url = "https://api.openai.com/v1/responses"
    prompt = (
        "You classify DJ tracks for a specific rekordbox library. "
        "Return compact JSON with keys rating, role, moods, color, priority, confidence, reasoning. "
        "Respect the proposed allowed values and only override when evidence is strong.\n\n"
        + json.dumps(record, ensure_ascii=False, default=str)
    )
    body = json.dumps(
        {
            "model": model,
            "input": prompt,
            "text": {"format": {"type": "json_object"}},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc)}
    text = ""
    for item in data.get("output", []):
        for part in item.get("content", []):
            if part.get("type") in {"output_text", "text"}:
                text += part.get("text", "")
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty Codex response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in Codex response")
    return json.loads(text[start : end + 1])


def optional_codex_review(
    enabled: bool,
    record: dict[str, Any],
    rules: dict[str, Any],
    model: str,
    timeout: int,
    use_search: bool,
) -> dict[str, Any] | None:
    if not enabled:
        return None

    prompt_payload = {
        "task": "Classify this track for the user's rekordbox library and DJ set dramaturgy.",
        "rules": rules,
        "track_context": record,
        "instructions": [
            "Return only JSON matching the schema.",
            "Do not change metadata Genre; genre_normalized means MyTag:Genre.",
            "Use 1-2 moods only.",
            "If web evidence is weak, rely on local library similarity and lower confidence.",
            "Prefer the user's dramaturgy over generic Beatport genre.",
        ],
    }
    prompt = (
        "You are a DJ library classification agent. Analyze the JSON below and return one JSON object only.\n\n"
        + json.dumps(prompt_payload, ensure_ascii=False, indent=2, default=str)
    )

    output_path = DEFAULT_OUTPUT_DIR / f"codex_track_decision_{record['content_id']}.json"
    codex_bin = "codex.cmd" if os.name == "nt" else "codex"
    cmd = [
        codex_bin,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--output-schema",
        str(CODEX_DECISION_SCHEMA),
        "--output-last-message",
        str(output_path),
    ]
    if model:
        cmd.extend(["--model", model])
    if use_search:
        cmd.append("--search")
    cmd.append("-")

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            cwd=str(PROJECT_DIR),
        )
    except Exception as exc:
        return {"error": str(exc)}

    raw = ""
    if output_path.exists():
        raw = output_path.read_text(encoding="utf-8", errors="replace")
    if not raw:
        raw = proc.stdout or proc.stderr
    try:
        parsed = extract_json_object(raw)
    except Exception as exc:
        return {
            "error": str(exc),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-2000:],
            "raw_tail": raw[-2000:],
        }
    parsed["_codex_returncode"] = proc.returncode
    return parsed


def make_backup(db_path: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"rekordbox_master_before_set_agent_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for suffix in ["", "-wal", "-shm"]:
        src = Path(str(db_path) + suffix)
        if src.exists():
            shutil.copy2(src, backup_dir / src.name)
    return backup_dir


def next_local_usn(db: Rekordbox6Database) -> int:
    values = []
    for model in (DjmdContent, DjmdMyTag, DjmdSongMyTag):
        for (value,) in db.session.query(model.rb_local_usn).all():
            if value is not None:
                values.append(int(value))
    return max(values or [0]) + 1


def next_numeric_id(existing: set[str]) -> str:
    import random

    while True:
        value = str(random.randint(10_000_000, 4_200_000_000))
        if value not in existing:
            existing.add(value)
            return value


def get_or_create_folder(db: Rekordbox6Database, name: str, usn: int, existing_ids: set[str]) -> tuple[Any, int]:
    folder = db.query(DjmdMyTag).filter(DjmdMyTag.ParentID == "root", DjmdMyTag.Name == name).first()
    if folder:
        return folder, usn
    seq = max([item.Seq or 0 for item in db.query(DjmdMyTag).filter(DjmdMyTag.ParentID == "root").all()] or [0]) + 1
    now = utc_now()
    folder = DjmdMyTag(
        ID=next_numeric_id(existing_ids),
        UUID=str(uuid.uuid4()),
        Seq=seq,
        Name=name,
        Attribute=1,
        ParentID="root",
        rb_data_status=0,
        rb_local_data_status=0,
        rb_local_deleted=0,
        rb_local_synced=0,
        usn=None,
        rb_local_usn=usn,
        created_at=now,
        updated_at=now,
    )
    db.add(folder)
    return folder, usn + 1


def get_or_create_tag(db: Rekordbox6Database, parent_id: str, name: str, usn: int, existing_ids: set[str]) -> tuple[Any, int]:
    tag = (
        db.query(DjmdMyTag)
        .filter(DjmdMyTag.ParentID == parent_id, DjmdMyTag.Name == name, DjmdMyTag.rb_local_deleted == 0)
        .first()
    )
    if tag:
        return tag, usn
    seq = max([item.Seq or 0 for item in db.query(DjmdMyTag).filter(DjmdMyTag.ParentID == parent_id).all()] or [0]) + 1
    now = utc_now()
    tag = DjmdMyTag(
        ID=next_numeric_id(existing_ids),
        UUID=str(uuid.uuid4()),
        Seq=seq,
        Name=name,
        Attribute=0,
        ParentID=parent_id,
        rb_data_status=0,
        rb_local_data_status=0,
        rb_local_deleted=0,
        rb_local_synced=0,
        usn=None,
        rb_local_usn=usn,
        created_at=now,
        updated_at=now,
    )
    db.add(tag)
    return tag, usn + 1


def apply_records(db: Rekordbox6Database, index: LibraryIndex, records: list[dict[str, Any]], db_path: Path) -> Path:
    backup = make_backup(db_path)
    existing_ids = {tag.ID for tag in db.query(DjmdMyTag).all()}
    usn = next_local_usn(db)

    parent_names = {"Genre": "Genre", "Situation": "Situation", "Components": "Components", "Priority": "Priority"}
    parents = {}
    for key, name in parent_names.items():
        parents[key], usn = get_or_create_folder(db, name, usn, existing_ids)

    for rec in records:
        if rec.get("confidence", 0) < rec.get("auto_apply_min", 0.82):
            continue
        content = db.query(DjmdContent).filter(DjmdContent.ID == rec["content_id"]).first()
        if not content:
            continue
        changed = False
        if content.Rating != rec["rating"]:
            content.Rating = rec["rating"]
            changed = True
        color_id = index.color_ids.get(rec["color"])
        if color_id and content.ColorID != color_id:
            content.ColorID = color_id
            changed = True
        if changed:
            content.rb_local_usn = usn
            content.updated_at = utc_now()
            usn += 1

        desired = {
            "Genre": [rec["genre_normalized"]],
            "Situation": [rec["role"]],
            "Components": rec["moods"],
            "Priority": [rec["priority"]],
        }
        for parent_key, names in desired.items():
            parent = parents[parent_key]
            for name in names:
                tag, usn = get_or_create_tag(db, parent.ID, name, usn, existing_ids)
                existing = (
                    db.query(DjmdSongMyTag)
                    .filter(DjmdSongMyTag.ContentID == content.ID, DjmdSongMyTag.MyTagID == tag.ID)
                    .first()
                )
                if existing:
                    continue
                now = utc_now()
                db.add(
                    DjmdSongMyTag(
                        ID=str(uuid.uuid4()),
                        UUID=str(uuid.uuid4()),
                        MyTagID=tag.ID,
                        ContentID=content.ID,
                        TrackNo=None,
                        rb_data_status=0,
                        rb_local_data_status=0,
                        rb_local_deleted=0,
                        rb_local_synced=0,
                        usn=None,
                        rb_local_usn=usn,
                        created_at=now,
                        updated_at=now,
                    )
                )
                usn += 1
    db.commit()
    return backup


def write_report(rows: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"set_agent_report_{stamp}.json"
    csv_path = output_dir / f"set_agent_report_{stamp}.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    fields = [
        "content_id",
        "artist",
        "title",
        "genre_normalized",
        "rating",
        "role",
        "moods",
        "color",
        "priority",
        "confidence",
        "needs_review",
        "similar_tracks",
        "evidence_sources",
        "reasoning",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{field: row.get(field) for field in fields},
                    "moods": ", ".join(row["moods"]),
                    "similar_tracks": " | ".join(
                        f"{item['artist']} - {item['title']} ({item['score']})" for item in row["similar_tracks"]
                    ),
                    "evidence_sources": ", ".join(row["evidence"].get("sources", [])),
                    "reasoning": " ; ".join(row["reasoning"]),
                }
            )
    return json_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Agentic classifier for new rekordbox tracks.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--similar-limit", type=int, default=5)
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--llm", action="store_true", help="Use optional OPENAI_API_KEY review.")
    parser.add_argument("--llm-model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--codex-review", action="store_true", help="Use local `codex exec` as the reasoning reviewer.")
    parser.add_argument("--codex-model", default=os.environ.get("CODEX_MODEL", "gpt-5.5"))
    parser.add_argument("--codex-timeout", type=int, default=180)
    parser.add_argument("--codex-search", action="store_true", help="Allow Codex CLI to use its native web search.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    rules = read_json(args.rules)
    db = Rekordbox6Database(path=args.db)
    index = LibraryIndex(db)
    classifier = SetClassifier(rules)
    web = WebEvidenceCollector(enabled=not args.no_web)
    candidates = index.candidates(args.days, args.limit)

    rows = []
    for view in candidates:
        evidence = web.collect(view.artist, view.content.Title)
        genre_normalized, genre_reasons = classifier.normalize_genre(view, evidence)
        moods, mood_reasons = classifier.moods(view, genre_normalized, evidence)
        rating, role, color, energy_reasons = classifier.rating_role_color(view, genre_normalized, moods)
        predicted = {"genre_normalized": genre_normalized, "moods": moods, "role": role}
        similar = similar_tracks(view, predicted, index.views, args.similar_limit)
        conf = confidence(evidence, similar, genre_reasons + mood_reasons + energy_reasons)
        priority = classifier.priority(rating, role, similar[0]["score"] if similar else 0, conf)
        record = {
            "content_id": view.content.ID,
            "artist": view.artist,
            "title": view.content.Title,
            "clean_title": clean_title(view.content.Title),
            "current_genre": view.genre,
            "label": view.label,
            "bpm": round(bpm_value(view.content), 2),
            "key": view.key,
            "genre_normalized": genre_normalized,
            "rating": rating,
            "role": role,
            "moods": moods,
            "color": color,
            "priority": priority,
            "similar_tracks": similar,
            "confidence": conf,
            "auto_apply_min": rules["confidence_thresholds"]["auto_apply_min"],
            "needs_review": conf < rules["confidence_thresholds"]["auto_apply_min"],
            "evidence": evidence,
            "reasoning": genre_reasons + mood_reasons + energy_reasons,
        }
        llm_result = optional_llm_review(args.llm, args.llm_model, record)
        if llm_result:
            record["llm_review"] = llm_result
        codex_result = optional_codex_review(
            args.codex_review,
            record,
            rules,
            args.codex_model,
            args.codex_timeout,
            args.codex_search,
        )
        if codex_result:
            record["baseline_decision"] = {
                "genre_normalized": record["genre_normalized"],
                "rating": record["rating"],
                "role": record["role"],
                "moods": record["moods"],
                "color": record["color"],
                "priority": record["priority"],
                "confidence": record["confidence"],
                "reasoning": record["reasoning"],
            }
            record["codex_review"] = codex_result
            if "error" not in codex_result:
                for key in ("genre_normalized", "rating", "role", "moods", "color", "priority", "confidence"):
                    if key in codex_result:
                        record[key] = codex_result[key]
                if "reasoning" in codex_result:
                    record["reasoning"] = codex_result["reasoning"]
                record["needs_review"] = record["confidence"] < rules["confidence_thresholds"]["auto_apply_min"]
        rows.append(record)

    json_path, csv_path = write_report(rows, args.output_dir)
    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "db": str(args.db),
        "candidates": len(rows),
        "json_report": str(json_path),
        "csv_report": str(csv_path),
        "web": not args.no_web,
        "llm": args.llm,
        "codex_review": args.codex_review,
        "codex_search": args.codex_search,
        "review_count": sum(1 for row in rows if row["needs_review"]),
    }
    if args.apply:
        summary["backup_dir"] = str(apply_records(db, index, rows, args.db))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Rekordbox fresh-track agent for this library.

Default mode is dry-run: it reads master.db, classifies fresh or untagged tracks,
and writes a JSON/CSV report. Use --apply to write Rating, Color, and MyTag links.

The script intentionally does not overwrite the metadata Genre field by default.
Genre_Normalized is written as a MyTag under the "Genre" MyTag folder.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYREKORDBOX_VENDOR = ROOT / "work" / "pyrekordbox_vendor"
if PYREKORDBOX_VENDOR.exists():
    sys.path.insert(0, str(PYREKORDBOX_VENDOR))

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
DEFAULT_OUTPUT_DIR = ROOT / "outputs"
BACKUP_ROOT = ROOT / "work" / "backups"

SET_ROLES = {"OPEN", "WARM", "JOURNEY", "MAIN", "PEAK", "CLOSE"}
MOODS = {"Deep", "Emotional", "Atmospheric", "Hypnotic", "Driving", "Dark", "Euphoric", "Vocal"}

TEST_COMMENTS = {
    "Indie Dance; WARM; Instrumental; Indie; Groovy",
    "Breaks; JOURNEY; Instrumental; Breaks; Atmospheric; Emotional; Journey",
    "Melodic House; JOURNEY; Instrumental; Atmospheric",
}

GENRE_RULES = [
    (("drum & bass", "dnb"), "Drum & Bass"),
    (("psy", "psy-trance", "psy trance"), "Psy-Trance"),
    (("hard techno",), "Hard Techno"),
    (("melodic house & techno", "melodic techno"), "Melodic Techno"),
    (("peak time", "driving techno"), "Techno"),
    (("progressive",), "Progressive House"),
    (("afro", "organic house"), "Afro / Organic House"),
    (("organic", "downtempo"), "Organic / Downtempo"),
    (("breaks", "breakbeat", "uk bass"), "Breaks"),
    (("indie dance", "nu disco"), "Indie Dance"),
    (("electronica", "ambient"), "Electronica"),
    (("deep house",), "Deep / Melodic House"),
    (("minimal", "deep tech"), "Minimal / Deep Tech"),
    (("trance",), "Trance"),
    (("dance", "pop"), "Dance / Pop"),
]

COLOR_BY_NAME = {
    "progressive": "Purple",
    "journey": "Purple",
    "emotional": "Blue",
    "deep": "Blue",
    "organic": "Green",
    "afro": "Green",
    "breaks": "Aqua",
    "main": "Orange",
    "peak": "Red",
    "classic": "Yellow",
    "close": "Pink",
    "closing": "Pink",
}


@dataclass
class TrackView:
    content: Any
    artist: str
    genre: str
    label: str
    key: str
    color: str | None
    tags: set[str]


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


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\s*[-_]\s*(www\..+|beatport|promo|clean|dirty)\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*\[(official|visualizer|audio|video|extended)\]\s*$", "", title, flags=re.I)
    return title.strip()


def normalize_genre(genre: str, title: str, artist: str, label: str) -> str:
    blob = lower_blob(genre, title, artist, label)
    for needles, result in GENRE_RULES:
        if any(needle in blob for needle in needles):
            return result
    return genre or "Unknown"


def infer_moods(title: str, artist: str, genre_normalized: str, label: str, bpm: float) -> list[str]:
    blob = lower_blob(title, artist, genre_normalized, label)
    scores = {mood: 0 for mood in MOODS}

    keyword_scores = {
        "Vocal": ("vocal", "feat.", "ft.", "voice", "sing", "female vocal", "male vocal"),
        "Deep": ("deep", "dub", "low", "sub", "night", "late"),
        "Emotional": ("emotional", "love", "tears", "soul", "heart", "swear", "feel"),
        "Atmospheric": ("atmos", "ambient", "cloud", "dream", "mirage", "space"),
        "Hypnotic": ("hypnotic", "loop", "ritual", "acid", "trance"),
        "Driving": ("driving", "run", "running", "power", "edge", "catalyst", "destructure"),
        "Dark": ("dark", "shadow", "black", "night", "noire"),
        "Euphoric": ("euphoric", "higher", "light", "sun", "heaven", "classic"),
    }
    for mood, needles in keyword_scores.items():
        scores[mood] += sum(2 for needle in needles if needle in blob)

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
    if "breaks" in genre_l:
        scores["Atmospheric"] += 1
    if bpm >= 126:
        scores["Driving"] += 1
    if bpm <= 120:
        scores["Deep"] += 1

    ranked = [mood for mood, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])) if score > 0]
    return ranked[:2] or ["Atmospheric"]


def infer_rating(genre_normalized: str, moods: list[str], bpm: float, title: str, label: str) -> tuple[int, str]:
    blob = lower_blob(genre_normalized, moods, title, label)
    score = 3
    reasons = []

    if any(token in blob for token in ["hard techno", "psy-trance", "drum & bass"]):
        score += 2
        reasons.append("high-intensity genre")
    elif any(token in blob for token in ["techno", "melodic techno"]):
        score += 1
        reasons.append("driving melodic/techno lane")
    elif any(token in blob for token in ["progressive", "journey"]):
        reasons.append("progressive/journey lane")
    elif any(token in blob for token in ["organic", "afro", "deep"]):
        score -= 1
        reasons.append("warm/deep lane")
    elif "electronica" in blob:
        score -= 2
        reasons.append("intro/electronica lane")

    if "Driving" in moods:
        score += 1
        reasons.append("driving mood")
    if "Dark" in moods and score >= 4:
        score += 1
        reasons.append("dark peak tension")
    if "Deep" in moods:
        score -= 1
        reasons.append("deep mood")
    if bpm >= 130:
        score += 1
        reasons.append("fast BPM")
    elif bpm <= 118:
        score -= 1
        reasons.append("low BPM")

    score = max(1, min(5, score))
    return score, ", ".join(reasons) or "neutral library rule"


def role_from_rating(rating: int, moods: list[str], genre_normalized: str) -> str:
    genre_l = genre_normalized.lower()
    if rating <= 1:
        return "OPEN"
    if rating == 2:
        return "WARM"
    if rating == 3:
        return "JOURNEY"
    if rating == 4:
        return "MAIN"
    if "Deep" in moods and "Emotional" in moods and "peak" not in genre_l:
        return "CLOSE"
    return "PEAK"


def color_for(role: str, moods: list[str], genre_normalized: str, title: str) -> str:
    blob = lower_blob(role, moods, genre_normalized, title)
    if role == "PEAK":
        return "Red"
    if role == "MAIN":
        return "Orange"
    if role == "CLOSE":
        return "Pink"
    for token, color in COLOR_BY_NAME.items():
        if token in blob:
            return color
    if role == "JOURNEY":
        return "Purple"
    if role == "WARM":
        return "Blue"
    return "Aqua"


def priority_for(rating: int, role: str, moods: list[str], similar_score: float) -> str:
    if rating >= 5 or (role == "MAIN" and similar_score >= 65):
        return "A"
    if rating >= 3:
        return "B"
    return "C"


def key_family(key: str) -> str:
    text = norm(key)
    if not text:
        return ""
    match = re.match(r"(\d+)([AB])", text, re.I)
    if match:
        return match.group(1)
    return text.rstrip("mM#b")


def bpm_value(content: Any) -> float:
    try:
        return float(content.BPM or 0) / 100.0
    except Exception:
        return 0.0


def make_backup(db_path: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"rekordbox_master_before_fresh_agent_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for suffix in ["", "-wal", "-shm"]:
        src = Path(str(db_path) + suffix)
        if src.exists():
            shutil.copy2(src, backup_dir / src.name)
    return backup_dir


def load_views(db: Rekordbox6Database) -> list[TrackView]:
    artists = {item.ID: item.Name for item in db.query(DjmdArtist).all()}
    genres = {item.ID: item.Name for item in db.query(DjmdGenre).all()}
    labels = {item.ID: item.Name for item in db.query(DjmdLabel).all()}
    keys = {item.ID: item.ScaleName for item in db.query(DjmdKey).all()}
    colors = {item.ID: item.Commnt for item in db.query(DjmdColor).all()}
    tag_names = {item.ID: item.Name for item in db.query(DjmdMyTag).filter(DjmdMyTag.rb_local_deleted == 0).all()}
    links_by_content: dict[str, set[str]] = {}
    for link in db.query(DjmdSongMyTag).all():
        if link.MyTagID in tag_names:
            links_by_content.setdefault(link.ContentID, set()).add(tag_names[link.MyTagID])

    return [
        TrackView(
            content=content,
            artist=artists.get(content.ArtistID, ""),
            genre=genres.get(content.GenreID, ""),
            label=labels.get(content.LabelID, ""),
            key=keys.get(content.KeyID, ""),
            color=colors.get(content.ColorID),
            tags=links_by_content.get(content.ID, set()),
        )
        for content in db.query(DjmdContent).all()
        if not content.rb_local_deleted
    ]


def is_fresh_or_needs_tags(view: TrackView, cutoff: dt.datetime | None) -> bool:
    created = parse_dt(view.content.created_at) or parse_dt(view.content.DateCreated)
    if cutoff and created and created >= cutoff:
        return True
    managed = SET_ROLES | MOODS | {"A", "B", "C"}
    return not (view.tags & managed)


def similar_tracks(target: TrackView, predicted: dict[str, Any], library: list[TrackView], limit: int) -> list[dict[str, Any]]:
    target_bpm = bpm_value(target.content)
    target_key = key_family(target.key)
    target_tags = set(predicted["moods"]) | {predicted["role"], predicted["genre_normalized"]}

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
            reasons.append("same genre lane")
        overlap = target_tags & other.tags
        if overlap:
            score += min(25, 8 * len(overlap))
            reasons.append("tag overlap: " + ", ".join(sorted(overlap)[:3]))
        if target_key and target_key == key_family(other.key):
            score += 10
            reasons.append("compatible key family")
        if predicted["role"] in other.tags:
            score += 10
            reasons.append("same set role")
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


def next_local_usn(db: Rekordbox6Database) -> int:
    values = []
    for model in (DjmdContent, DjmdMyTag, DjmdSongMyTag):
        for (value,) in db.session.query(model.rb_local_usn).all():
            if value is not None:
                values.append(int(value))
    return max(values or [0]) + 1


def next_numeric_id(existing: set[str]) -> str:
    # Keep IDs numeric because rekordbox UI is pickier about MyTag IDs than the DB schema.
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


def get_or_create_tag(
    db: Rekordbox6Database,
    parent_id: str,
    name: str,
    usn: int,
    existing_ids: set[str],
) -> tuple[Any, int]:
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


def apply_recommendations(db: Rekordbox6Database, recommendations: list[dict[str, Any]], db_path: Path) -> Path:
    backup = make_backup(db_path)
    colors = {item.Commnt: item.ID for item in db.query(DjmdColor).all()}
    existing_ids = {item.ID for item in db.query(DjmdMyTag).all()}
    usn = next_local_usn(db)

    parent_names = {
        "Genre": "Genre",
        "Situation": "Situation",
        "Components": "Components",
        "Priority": "Priority",
    }
    parents = {}
    for key, name in parent_names.items():
        parents[key], usn = get_or_create_folder(db, name, usn, existing_ids)

    for rec in recommendations:
        content = db.query(DjmdContent).filter(DjmdContent.ID == rec["content_id"]).first()
        if not content:
            continue

        changed = False
        if content.Rating != rec["rating"]:
            content.Rating = rec["rating"]
            changed = True
        color_id = colors.get(rec["color"])
        if color_id and content.ColorID != color_id:
            content.ColorID = color_id
            changed = True
        if (content.Commnt or "") in TEST_COMMENTS:
            content.Commnt = ""
            changed = True
        if changed:
            content.updated_at = utc_now()
            content.rb_local_usn = usn
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


def write_reports(rows: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"fresh_track_agent_report_{stamp}.json"
    csv_path = output_dir / f"fresh_track_agent_report_{stamp}.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "content_id",
            "artist",
            "title",
            "clean_title",
            "current_genre",
            "genre_normalized",
            "rating",
            "role",
            "moods",
            "color",
            "priority",
            "similar_tracks",
            "reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key) for key in fieldnames},
                    "moods": ", ".join(row["moods"]),
                    "similar_tracks": " | ".join(
                        f"{item['artist']} - {item['title']} ({item['score']})" for item in row["similar_tracks"]
                    ),
                }
            )
    return json_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify fresh rekordbox tracks for set role, vibe, and priority.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--days", type=int, default=30, help="Treat tracks created within N days as fresh.")
    parser.add_argument("--since", type=str, default="", help="Override --days with YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tracks processed.")
    parser.add_argument("--apply", action="store_true", help="Write Rating, Color, and MyTag links to master.db.")
    parser.add_argument("--similar-limit", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.since:
        cutoff = dt.datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    elif args.days > 0:
        cutoff = utc_now() - dt.timedelta(days=args.days)
    else:
        cutoff = None

    db = Rekordbox6Database(path=args.db)
    views = load_views(db)
    candidates = [view for view in views if is_fresh_or_needs_tags(view, cutoff)]
    candidates.sort(key=lambda view: str(view.content.created_at or ""), reverse=True)
    if args.limit:
        candidates = candidates[: args.limit]

    report = []
    for view in candidates:
        content = view.content
        bpm = bpm_value(content)
        genre_normalized = normalize_genre(view.genre, content.Title, view.artist, view.label)
        moods = infer_moods(content.Title, view.artist, genre_normalized, view.label, bpm)
        rating, reason = infer_rating(genre_normalized, moods, bpm, content.Title, view.label)
        role = role_from_rating(rating, moods, genre_normalized)
        color = color_for(role, moods, genre_normalized, content.Title)

        partial = {"genre_normalized": genre_normalized, "moods": moods, "role": role}
        similar = similar_tracks(view, partial, views, args.similar_limit)
        best_score = similar[0]["score"] if similar else 0
        priority = priority_for(rating, role, moods, best_score)

        report.append(
            {
                "content_id": content.ID,
                "artist": view.artist,
                "title": content.Title,
                "clean_title": clean_title(content.Title),
                "current_genre": view.genre,
                "genre_normalized": genre_normalized,
                "bpm": round(bpm, 2) if bpm else None,
                "key": view.key,
                "label": view.label,
                "rating": rating,
                "role": role,
                "moods": moods,
                "color": color,
                "priority": priority,
                "similar_tracks": similar,
                "reason": reason,
            }
        )

    json_path, csv_path = write_reports(report, args.output_dir)
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "db": str(args.db),
        "candidates": len(report),
        "json_report": str(json_path),
        "csv_report": str(csv_path),
    }
    if args.apply and report:
        result["backup_dir"] = str(apply_recommendations(db, report, args.db))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

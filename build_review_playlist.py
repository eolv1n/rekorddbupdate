"""
Build a rekordbox playlist with tracks that look worth manual review.

The script does not change Rating, Color, or MyTag assignments. It creates a
playlist and writes a CSV report explaining why each track was selected.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import shutil
import sys
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
    DjmdPlaylist,
    DjmdSongMyTag,
    Rekordbox6Database,
)


DEFAULT_DB = Path(r"C:\Users\Admin\AppData\Roaming\Pioneer\rekordbox\master.db")
DEFAULT_REPORT_DIR = PROJECT_DIR / "reports"
DEFAULT_BACKUP_DIR = PROJECT_DIR / "backups"
ROLE_TAGS = {"OPEN", "WARM", "JOURNEY", "MAIN", "PEAK", "CLOSE", "WARM UP", "OPEN / INTRO", "MAIN TIME"}
GENRE_HINTS = {
    "Psy-Trance",
    "Trance",
    "Organic House",
    "Afro House",
    "Organic / Downtempo",
    "Progressive House",
    "Indie Dance",
    "Future House",
    "Breaks",
    "Drum & Bass",
    "Melodic Techno",
    "Techno",
    "Deep House",
    "Minimal",
    "Electronica",
    "Ambient",
}


@dataclass
class Candidate:
    score: int
    content_id: str
    artist: str
    title: str
    rating: int
    color: str
    genre: str
    bpm: str
    key: str
    tags: str
    reasons: list[str]


def norm(value: Any) -> str:
    return str(value or "").strip()


def lower_blob(*values: Any) -> str:
    return " ".join(norm(value).lower() for value in values if value is not None)


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_db(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"rekordbox_master_before_review_playlist_{now_stamp()}.db"
    shutil.copy2(db_path, target)
    return target


def load_maps(db: Rekordbox6Database) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str], dict[str, str], dict[str, set[str]]]:
    artists = {item.ID: norm(item.Name) for item in db.query(DjmdArtist).all()}
    genres = {item.ID: norm(item.Name) for item in db.query(DjmdGenre).all()}
    labels = {item.ID: norm(item.Name) for item in db.query(DjmdLabel).all()}
    keys = {item.ID: norm(item.ScaleName) for item in db.query(DjmdKey).all()}
    colors = {item.ID: norm(item.Commnt) for item in db.query(DjmdColor).all()}
    tag_names = {item.ID: norm(item.Name) for item in db.query(DjmdMyTag).filter(DjmdMyTag.rb_local_deleted == 0).all()}
    tags_by_content: dict[str, set[str]] = {}
    for link in db.query(DjmdSongMyTag).all():
        name = tag_names.get(link.MyTagID)
        if name:
            tags_by_content.setdefault(link.ContentID, set()).add(name)
    return artists, genres, labels, keys, colors, tags_by_content


def tag_has(tags: set[str], *names: str) -> bool:
    lowered = {tag.lower() for tag in tags}
    return any(name.lower() in lowered for name in names)


def any_text(text: str, *needles: str) -> bool:
    return any(needle.lower() in text for needle in needles)


def score_track(content: Any, artist: str, genre: str, label: str, key: str, color: str, tags: set[str]) -> Candidate | None:
    title = norm(content.Title)
    rating = int(content.Rating or 0)
    bpm = norm(content.BPM)
    blob = lower_blob(artist, title, genre, label, *tags)
    reasons: list[str] = []
    score = 0

    if rating <= 2 and tag_has(tags, "PEAK", "MAIN", "MAIN TIME"):
        score += 100
        reasons.append("low rating with PEAK/MAIN role")
    if rating <= 2 and color == "Red":
        score += 100
        reasons.append("low rating with Red color")
    if color == "Red" and tag_has(tags, "OPEN", "OPEN / INTRO", "WARM", "WARM UP"):
        score += 95
        reasons.append("Red color with OPEN/WARM role")
    if any_text(blob, "psy-trance", "psy trance") and color == "Red":
        score += 90
        reasons.append("Psy-Trance marked Red; current taste says psy is not a Red lane")
    if any_text(blob, "organic", "afro") and tag_has(tags, "PEAK"):
        score += 85
        reasons.append("Organic/Afro with PEAK role")
    if any_text(blob, "organic", "afro") and rating >= 5:
        score += 80
        reasons.append("Organic/Afro with rating 5")
    if any_text(blob, "future house") and color == "Yellow":
        score += 80
        reasons.append("Future House marked Yellow")
    if any_text(blob, "breaks", "breakbeat", "uk bass") and color == "Red":
        score += 55
        reasons.append("Breaks marked Red; review against Aqua/Orange/Blue split")
    if any_text(blob, "drum & bass", "dnb") and color == "Red":
        score += 55
        reasons.append("Drum & Bass marked Red; DnB should be mood-based")
    if any_text(blob, "indie dance") and color == "Green":
        score += 50
        reasons.append("Indie Dance still Green after recent correction")
    if any_text(blob, "ambient", "downtempo", "chillout", "beatless") and (rating >= 4 or color == "Red"):
        score += 70
        reasons.append("Ambient/downtempo looks too energetic")
    if "melodic techno" in blob and color == "Red" and rating <= 3:
        score += 35
        reasons.append("Melodic Techno Red with modest rating; check if it is truly peak-time")
    if "progressive house" in blob and color == "Red" and rating <= 3:
        score += 25
        reasons.append("Progressive can be diverse, but Red/rating 3 deserves a quick listen")

    role_count = len(tags & ROLE_TAGS)
    if role_count > 2:
        score += 35
        reasons.append("too many role tags")
    genre_count = len(tags & GENRE_HINTS)
    if genre_count > 3:
        score += 25
        reasons.append("too many normalized genre tags")
    if rating == 0 and (color or tags):
        score += 25
        reasons.append("has color/tags but no rating")
    if rating >= 5 and color not in {"Red", "Orange"}:
        score += 30
        reasons.append("rating 5 outside Red/Orange")

    if score <= 0:
        return None
    return Candidate(
        score=score,
        content_id=content.ID,
        artist=artist,
        title=title,
        rating=rating,
        color=color,
        genre=genre,
        bpm=bpm,
        key=key,
        tags="; ".join(sorted(tags)),
        reasons=reasons,
    )


def remove_existing_playlist(db: Rekordbox6Database, name: str) -> int:
    removed = 0
    existing = db.query(DjmdPlaylist).filter(DjmdPlaylist.Name == name).all()
    for playlist in existing:
        db.delete_playlist(playlist)
        removed += 1
    return removed


def write_report(path: Path, candidates: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "rank",
                "score",
                "artist",
                "title",
                "rating",
                "color",
                "metadata_genre",
                "bpm",
                "key",
                "tags",
                "reasons",
                "content_id",
            ],
        )
        writer.writeheader()
        for index, item in enumerate(candidates, start=1):
            writer.writerow(
                {
                    "rank": index,
                    "score": item.score,
                    "artist": item.artist,
                    "title": item.title,
                    "rating": item.rating,
                    "color": item.color,
                    "metadata_genre": item.genre,
                    "bpm": item.bpm,
                    "key": item.key,
                    "tags": item.tags,
                    "reasons": " | ".join(item.reasons),
                    "content_id": item.content_id,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a rekordbox playlist with likely tag/rating/color discrepancies.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--name", default="Codex review - discrepancies 200")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-existing", action="store_true", help="Do not replace an existing playlist with the same name.")
    args = parser.parse_args()

    db_path = args.db.expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    backup_path = None if args.dry_run else backup_db(db_path, args.backup_dir)
    db = Rekordbox6Database(db_path)
    artists, genres, labels, keys, colors, tags_by_content = load_maps(db)

    candidates: list[Candidate] = []
    for content in db.query(DjmdContent).filter(DjmdContent.rb_local_deleted == 0).all():
        artist = artists.get(content.ArtistID, "")
        genre = genres.get(content.GenreID, "")
        label = labels.get(content.LabelID, "")
        key = keys.get(content.KeyID, "")
        color = colors.get(content.ColorID, "")
        tags = tags_by_content.get(content.ID, set())
        candidate = score_track(content, artist, genre, label, key, color, tags)
        if candidate:
            candidates.append(candidate)

    candidates.sort(key=lambda item: (-item.score, item.artist.lower(), item.title.lower()))
    selected = candidates[: args.limit]
    report_path = args.report_dir / f"review_playlist_discrepancies_{now_stamp()}.csv"
    write_report(report_path, selected)

    if not args.dry_run:
        if not args.keep_existing:
            remove_existing_playlist(db, args.name)
        playlist = db.create_playlist(args.name)
        for index, item in enumerate(selected, start=1):
            db.add_to_playlist(playlist, item.content_id, track_no=index)
        db.commit()
    db.close()

    print(f"candidates_total={len(candidates)}")
    print(f"selected={len(selected)}")
    print(f"report={report_path}")
    if backup_path:
        print(f"backup={backup_path}")
    if not args.dry_run:
        print(f"playlist={args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

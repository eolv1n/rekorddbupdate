"""
Synchronize rekordbox date-added fields from the file creation date on disk.

This updates `DateCreated` from the file creation date resolved through
`FolderPath`. It never changes `created_at`, which is an internal database
timestamp. `StockDate` is left unchanged by default because many existing tracks
have harmless one-day `StockDate` differences.

Dry-run is the default. Use `--apply` only after closing rekordbox.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import sys
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

from pyrekordbox.db6 import DjmdArtist, DjmdContent, Rekordbox6Database  # noqa: E402


DEFAULT_DB = Path(r"C:\Users\Admin\AppData\Roaming\Pioneer\rekordbox\master.db")
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "reports"
BACKUP_ROOT = PROJECT_DIR / "backups"


def parse_date(value: Any) -> dt.date | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def make_backup(db_path: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"rekordbox_master_before_date_sync_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for suffix in ("", "-shm", "-wal"):
        src = Path(str(db_path) + suffix)
        if src.exists():
            shutil.copy2(src, backup_dir / src.name)
    return backup_dir


def next_local_usn(db: Rekordbox6Database) -> int:
    values = []
    for (value,) in db.session.query(DjmdContent.rb_local_usn).all():
        if value is not None:
            values.append(int(value))
    return max(values or [0]) + 1


def collect_changes(db: Rekordbox6Database, include_stock: bool) -> list[dict[str, Any]]:
    artists = {item.ID: item.Name for item in db.query(DjmdArtist).all()}
    rows = []
    for content in db.query(DjmdContent).all():
        if content.rb_local_deleted:
            continue
        path = Path(str(content.FolderPath or ""))
        if not path.exists():
            continue
        file_date = dt.datetime.fromtimestamp(path.stat().st_ctime).date()
        date_created = parse_date(content.DateCreated)
        stock_date = parse_date(content.StockDate)
        date_diff = date_created != file_date
        stock_diff = include_stock and stock_date != file_date
        if not date_diff and not stock_diff:
            continue
        rows.append(
            {
                "content_id": content.ID,
                "artist": artists.get(content.ArtistID, ""),
                "title": content.Title,
                "path": str(path),
                "file_created": file_date.isoformat(),
                "old_DateCreated": date_created.isoformat() if date_created else str(content.DateCreated),
                "old_StockDate": stock_date.isoformat() if stock_date else str(content.StockDate),
            }
        )
    rows.sort(key=lambda row: (row["file_created"], row["artist"], row["title"]), reverse=True)
    return rows


def write_report(rows: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"date_added_sync_report_{stamp}.json"
    csv_path = output_dir / f"date_added_sync_report_{stamp}.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = ["content_id", "artist", "title", "file_created", "old_DateCreated", "old_StockDate", "path"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return json_path, csv_path


def apply_changes(
    db: Rekordbox6Database,
    rows: list[dict[str, Any]],
    db_path: Path,
    include_stock: bool,
) -> dict[str, Any]:
    backup = make_backup(db_path)
    rows_by_id = {row["content_id"]: row for row in rows}
    usn = next_local_usn(db)
    updated = 0
    now = dt.datetime.now(dt.timezone.utc)
    for content in db.query(DjmdContent).filter(DjmdContent.ID.in_(rows_by_id.keys())).all():
        file_date = dt.date.fromisoformat(rows_by_id[content.ID]["file_created"])
        content.DateCreated = file_date
        if include_stock:
            content.StockDate = file_date
        content.rb_local_usn = usn
        content.updated_at = now
        usn += 1
        updated += 1
    db.commit()
    return {"backup_dir": str(backup), "updated": updated}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync rekordbox DateCreated from file creation date.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--include-stock", action="store_true", help="Also sync StockDate. Not recommended broadly.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = Rekordbox6Database(path=args.db)
    rows = collect_changes(db, include_stock=args.include_stock)
    json_path, csv_path = write_report(rows, args.output_dir)
    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "db": str(args.db),
        "changes": len(rows),
        "include_stock": args.include_stock,
        "json_report": str(json_path),
        "csv_report": str(csv_path),
    }
    if args.apply and rows:
        summary.update(apply_changes(db, rows, args.db, include_stock=args.include_stock))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

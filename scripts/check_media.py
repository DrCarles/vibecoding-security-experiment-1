"""Compare image files on the media volume with the paths stored in the database.

Runs inside the backend container (it has both the database and the media volume):
    docker compose exec -T backend python - < scripts/check_media.py

Reports files referenced in the database but missing on disk (broken images) and
files on disk that nothing references (orphans left behind, safe to delete).
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

media = Path(os.environ.get("MEDIA_DIR", "/data/media"))
engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    referenced = {
        row[0]
        for row in conn.execute(
            text(
                "SELECT image_path FROM posts WHERE image_path IS NOT NULL "
                "UNION ALL SELECT avatar_path FROM users WHERE avatar_path IS NOT NULL"
            )
        )
    }

on_disk = {p.relative_to(media).as_posix() for p in media.rglob("*") if p.is_file()}
total_bytes = sum((media / p).stat().st_size for p in on_disk)

missing = sorted(referenced - on_disk)
orphans = sorted(on_disk - referenced)

print(f"Media directory : {media}")
print(f"Files on disk   : {len(on_disk)} ({total_bytes / 1024 / 1024:.2f} MB)")
print(f"Referenced in DB: {len(referenced)}")
print(f"Missing files   : {len(missing)}")
for p in missing:
    print(f"  MISSING {p}")
print(f"Orphaned files  : {len(orphans)}")
for p in orphans:
    print(f"  ORPHAN  {p}")

sys.exit(1 if missing else 0)

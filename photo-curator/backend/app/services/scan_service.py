"""Recursive image directory scanner."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Image, ScanJob

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tiff", ".tif"}


def _open_image_safe(path: str):
    """Open an image as RGB PIL Image. Registers HEIC opener if needed."""
    from PIL import Image as PILImage
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    return PILImage.open(path).convert("RGB")


def _count_images(root: str) -> int:
    """Quick pre-scan to count supported images (for progress bar total)."""
    count = 0
    for entry in os.scandir(root):
        if entry.is_dir(follow_symlinks=False):
            count += _count_images(entry.path)
        elif entry.is_file() and Path(entry.name).suffix.lower() in SUPPORTED_EXTENSIONS:
            count += 1
    return count


async def scan_directory(
    root: str,
    session: AsyncSession,
    score_queue: asyncio.Queue,
    job_id: int,
) -> int:
    """
    Recursively scan root for images. Inserts new Image rows and queues them
    for scoring. Skips already-scored paths.
    Returns count of newly queued images.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise ValueError(f"Directory not found: {root}")

    queued = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async def _walk(directory: str) -> None:
        nonlocal queued
        try:
            entries = list(os.scandir(directory))
        except PermissionError:
            return
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                await _walk(entry.path)
            elif entry.is_file():
                ext = Path(entry.name).suffix.lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                path_str = entry.path

                # Skip if already in DB and scored
                existing = await session.execute(
                    select(Image.id, Image.status).where(Image.path == path_str)
                )
                row = existing.one_or_none()
                if row and row.status == "scored":
                    continue

                try:
                    stat = entry.stat()
                    file_size = stat.st_size
                except OSError:
                    file_size = 0

                if row is None:
                    img_row = Image(
                        path=path_str,
                        filename=entry.name,
                        extension=ext.lstrip("."),
                        file_size_bytes=file_size,
                        status="pending",
                        decision="undecided",
                        scanned_at=now,
                    )
                    session.add(img_row)
                    await session.flush()
                    img_id = img_row.id
                else:
                    img_id = row.id
                    await session.execute(
                        __import__("sqlalchemy").update(Image)
                        .where(Image.id == img_id)
                        .values(status="pending")
                    )

                await score_queue.put((img_id, path_str))
                queued += 1

                # Commit in small batches to avoid long transactions
                if queued % 100 == 0:
                    await session.commit()

    await _walk(str(root_path))
    await session.commit()

    # Update job total
    from sqlalchemy import update
    await session.execute(
        update(ScanJob).where(ScanJob.id == job_id).values(total_files=queued)
    )
    await session.commit()

    return queued


def test_path_access(path: str) -> dict:
    """
    Check if path exists and is readable. Returns dict with accessible bool,
    file_count, and optional error_message.
    """
    p = Path(path)
    if not p.exists():
        return {"accessible": False, "file_count": 0, "error": f"Path not found: {path}"}
    if not p.is_dir():
        return {"accessible": False, "file_count": 0, "error": f"Not a directory: {path}"}
    if not os.access(str(p), os.R_OK):
        return {"accessible": False, "file_count": 0, "error": "Permission denied — can't read this folder"}
    try:
        count = _count_images(str(p))
        return {"accessible": True, "file_count": count, "error": None}
    except Exception as e:
        return {"accessible": False, "file_count": 0, "error": str(e)}

"""Album export to print-ready JPEGs."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_session
from ..services.export_service import export_album

router = APIRouter(prefix="/api/albums", tags=["export"])

# Simple in-memory export job tracking (single-user app)
_export_jobs: dict[int, dict] = {}
_export_job_counter = 0


class ExportRequest(BaseModel):
    output_dir: str | None = None


@router.post("/{album_id}/export")
async def trigger_export(
    album_id: int,
    req: ExportRequest,
    session: AsyncSession = Depends(get_session),
):
    global _export_job_counter
    settings = get_settings()

    output_dir = req.output_dir
    if not output_dir:
        from ..database import Album
        from sqlalchemy import select
        album = (await session.execute(select(Album).where(Album.id == album_id))).scalar_one_or_none()
        if not album:
            raise HTTPException(404, "Album not found")
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        safe_name = album.name.replace(" ", "_")[:40]
        output_dir = str(Path(settings.image_dir).parent / "exports" / f"{safe_name}_{ts}")

    _export_job_counter += 1
    job_id = _export_job_counter
    _export_jobs[job_id] = {"status": "running", "album_id": album_id,
                             "output_dir": output_dir, "exported_files": [], "error": None}

    async def _run():
        try:
            from ..database import AsyncSessionLocal
            async with AsyncSessionLocal() as s:
                files = await export_album(album_id, output_dir, s, settings.export_dpi)
            _export_jobs[job_id]["status"] = "complete"
            _export_jobs[job_id]["exported_files"] = files
        except Exception as e:
            _export_jobs[job_id]["status"] = "failed"
            _export_jobs[job_id]["error"] = str(e)

    asyncio.create_task(_run())
    return {"job_id": job_id, "output_dir": output_dir}


@router.get("/{album_id}/export/status")
async def export_status(album_id: int):
    # Find most recent job for this album
    for jid in sorted(_export_jobs.keys(), reverse=True):
        if _export_jobs[jid]["album_id"] == album_id:
            j = _export_jobs[jid]
            return {
                "job_id": jid,
                "status": j["status"],
                "output_dir": j["output_dir"],
                "file_count": len(j["exported_files"]),
                "error": j["error"],
            }
    raise HTTPException(404, "No export job found for this album")

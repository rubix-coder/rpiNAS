"""Image gallery, scan, thumbnail, and original endpoints."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image as PILImage
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Image as ImageORM, ScanJob, get_session
from ..models.scorer import stars_from_score
from ..services.scan_service import scan_directory

router = APIRouter(prefix="/api/images", tags=["images"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class ImageSummary(BaseModel):
    id: int
    filename: str
    thumbnail_url: str
    original_url: str
    composite_score: float | None
    aesthetic_score: float | None
    sharpness_score: float | None
    exposure_score: float | None
    face_count: int
    stars: int
    decision: str
    is_duplicate: bool
    status: str
    width: int | None
    height: int | None
    captured_at: datetime | None

    model_config = {"from_attributes": True}


class ImageDetail(ImageSummary):
    path: str
    phash: str | None
    error_message: str | None
    scored_at: datetime | None
    scanned_at: datetime


class GalleryResponse(BaseModel):
    items: list[ImageSummary]
    total: int
    page: int
    limit: int
    pages: int


class ScanJobSchema(BaseModel):
    id: int
    status: str
    total_files: int
    scored_files: int
    progress_pct: float
    root_path: str
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class ScanRequest(BaseModel):
    directory: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _thumbnail_cache_path(image_id: int, db_path: str) -> str:
    cache_dir = Path(db_path).parent / "thumbnails"
    cache_dir.mkdir(exist_ok=True)
    return str(cache_dir / f"{image_id}.jpg")


def _to_summary(img: ImageORM, db_path: str) -> ImageSummary:
    comp = img.composite_score
    return ImageSummary(
        id=img.id,
        filename=img.filename,
        thumbnail_url=f"/api/images/{img.id}/thumbnail",
        original_url=f"/api/images/{img.id}/original",
        composite_score=comp,
        aesthetic_score=img.aesthetic_score,
        sharpness_score=img.sharpness_score,
        exposure_score=img.exposure_score,
        face_count=img.face_count or 0,
        stars=stars_from_score(comp) if comp is not None else 0,
        decision=img.decision,
        is_duplicate=img.is_duplicate,
        status=img.status,
        width=img.width,
        height=img.height,
        captured_at=img.captured_at,
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/scan")
async def start_scan(
    req: ScanRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    from ..config import get_settings
    settings = get_settings()
    directory = req.directory or settings.image_dir

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    job = ScanJob(root_path=directory, started_at=now, status="running")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    score_queue: asyncio.Queue = request.app.state.score_queue

    async def _run_scan():
        try:
            await scan_directory(directory, session, score_queue, job.id)
            from sqlalchemy import update
            await session.execute(
                update(ScanJob).where(ScanJob.id == job.id).values(
                    status="complete",
                    finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            await session.commit()
        except Exception as e:
            from sqlalchemy import update
            await session.execute(
                update(ScanJob).where(ScanJob.id == job.id).values(status="failed")
            )
            await session.commit()

    asyncio.create_task(_run_scan())
    return {"job_id": job.id}


@router.get("/scan/{job_id}", response_model=ScanJobSchema)
async def get_scan_job(job_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ScanJob).where(ScanJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Scan job not found")
    pct = 0.0
    if job.total_files and job.total_files > 0:
        pct = round(job.scored_files / job.total_files * 100, 1)
    return ScanJobSchema(
        id=job.id,
        status=job.status,
        total_files=job.total_files,
        scored_files=job.scored_files,
        progress_pct=pct,
        root_path=job.root_path,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.get("", response_model=GalleryResponse)
async def list_images(
    page: int = 1,
    limit: int = 50,
    sort: str = "composite_score",
    order: str = "desc",
    decision: str | None = None,
    min_score: float = 0.0,
    exclude_duplicates: bool = True,
    session: AsyncSession = Depends(get_session),
):
    from ..config import get_settings
    settings = get_settings()

    q = select(ImageORM).where(ImageORM.status == "scored")
    if decision:
        q = q.where(ImageORM.decision == decision)
    if min_score > 0:
        q = q.where(ImageORM.composite_score >= min_score)
    if exclude_duplicates:
        q = q.where(ImageORM.is_duplicate == False)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.execute(count_q)).scalar_one()

    sort_col = getattr(ImageORM, sort, ImageORM.composite_score)
    if order == "desc":
        sort_col = sort_col.desc()
    q = q.order_by(sort_col).offset((page - 1) * limit).limit(limit)

    rows = (await session.execute(q)).scalars().all()
    items = [_to_summary(r, settings.db_path) for r in rows]

    return GalleryResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=max(1, -(-total // limit)),
    )


@router.get("/{image_id}/thumbnail")
async def get_thumbnail(image_id: int, session: AsyncSession = Depends(get_session)):
    from ..config import get_settings
    settings = get_settings()

    result = await session.execute(select(ImageORM).where(ImageORM.id == image_id))
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(404, "Image not found")

    cache_path = _thumbnail_cache_path(image_id, settings.db_path)
    if not os.path.exists(cache_path):
        try:
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                pass
            pil = PILImage.open(img.path).convert("RGB")
            pil.thumbnail((settings.thumbnail_size, settings.thumbnail_size), PILImage.LANCZOS)
            pil.save(cache_path, "JPEG", quality=85)
        except Exception:
            raise HTTPException(500, "Could not generate thumbnail")

    return FileResponse(cache_path, media_type="image/jpeg")


@router.get("/{image_id}/original")
async def get_original(image_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ImageORM).where(ImageORM.id == image_id))
    img = result.scalar_one_or_none()
    if not img or not os.path.exists(img.path):
        raise HTTPException(404, "Image not found")
    return FileResponse(img.path)


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image(image_id: int, session: AsyncSession = Depends(get_session)):
    from ..config import get_settings
    settings = get_settings()
    result = await session.execute(select(ImageORM).where(ImageORM.id == image_id))
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(404, "Image not found")
    base = _to_summary(img, settings.db_path)
    return ImageDetail(
        **base.model_dump(),
        path=img.path,
        phash=img.phash,
        error_message=img.error_message,
        scored_at=img.scored_at,
        scanned_at=img.scanned_at,
    )

"""Background GPU+CPU scoring worker."""
from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
from PIL import Image
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ..config import Settings
from ..database import Image as ImageORM, ScanJob
from ..models.scorer import (
    AestheticScorer,
    ScoreResult,
    compute_exposure,
    compute_phash,
    compute_sharpness,
    composite_score,
    detect_faces,
    read_exif_date,
)

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="scorer")


def _open_and_measure(path: str) -> tuple[Image.Image, dict] | None:
    """Open image and compute all CPU-side metrics. Returns None on failure."""
    try:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        import cv2

        pil_img = Image.open(path).convert("RGB")
        w, h = pil_img.size
        captured_at = read_exif_date(pil_img)
        phash = compute_phash(pil_img)
        exposure = compute_exposure(pil_img)

        cv2_img = np.array(pil_img)
        gray = cv2.cvtColor(cv2_img, cv2.COLOR_RGB2GRAY)
        sharpness = compute_sharpness(gray)
        face_count, face_rects = detect_faces(cv2_img)

        return pil_img, {
            "width": w, "height": h, "captured_at": captured_at,
            "phash": phash, "exposure": exposure, "sharpness": sharpness,
            "face_count": face_count, "face_rects": face_rects,
        }
    except Exception as e:
        logger.warning("Failed to open %s: %s", path, e)
        return None


def _find_duplicate(phash: str, existing_hashes: dict[str, int], max_dist: int) -> int | None:
    """Find an existing image ID whose pHash is within max_dist Hamming distance."""
    import imagehash
    try:
        h = imagehash.hex_to_hash(phash)
        for existing_phash, existing_id in existing_hashes.items():
            if imagehash.hex_to_hash(existing_phash) - h <= max_dist:
                return existing_id
    except Exception:
        pass
    return None


async def scoring_worker(
    score_queue: asyncio.Queue,
    scorer: AestheticScorer,
    settings: Settings,
    db_engine: AsyncEngine,
) -> None:
    """Runs forever, draining score_queue in batches."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    loop = asyncio.get_event_loop()

    weights = {
        "aesthetic": settings.aesthetic_weight,
        "sharpness": settings.sharpness_weight,
        "exposure": settings.exposure_weight,
        "face_bonus": settings.face_bonus_weight,
    }

    # Cache of phash→image_id for duplicate detection (grows as we score)
    phash_cache: dict[str, int] = {}

    while True:
        # Drain up to batch_size items
        batch_items: list[tuple[int, str]] = []
        try:
            item = await score_queue.get()
            batch_items.append(item)
            try:
                while len(batch_items) < settings.batch_size:
                    batch_items.append(score_queue.get_nowait())
            except asyncio.QueueEmpty:
                pass
        except asyncio.CancelledError:
            return

        if not batch_items:
            continue

        img_ids = [i[0] for i in batch_items]
        paths = [i[1] for i in batch_items]

        # Step 1 + CPU metrics in thread pool
        cpu_results = await loop.run_in_executor(
            _executor,
            lambda: [_open_and_measure(p) for p in paths],
        )

        valid = [(img_ids[i], paths[i], cpu_results[i]) for i in range(len(paths)) if cpu_results[i] is not None]
        failed_ids = [img_ids[i] for i in range(len(paths)) if cpu_results[i] is None]

        if valid:
            pil_images = [v[2][0] for v in valid]

            # Step 4: GPU aesthetic scoring + scene classification
            try:
                aesthetic_scores, scene_slugs = await loop.run_in_executor(
                    _executor, scorer.score_batch, pil_images
                )
            except Exception as e:
                logger.error("GPU scoring failed: %s", e)
                aesthetic_scores = [5.0] * len(pil_images)
                scene_slugs = ["unknown_scene"] * len(pil_images)

            # Step 5–8: compute composite, detect duplicates, write DB
            async with session_factory() as session:
                job_ids_to_update: set[int] = set()

                for idx, (img_id, path, (pil_img, cpu)) in enumerate(valid):
                    aes = aesthetic_scores[idx]
                    scene = scene_slugs[idx]
                    sharp = cpu["sharpness"]
                    exp = cpu["exposure"]
                    face_count = cpu["face_count"]
                    face_rects = cpu["face_rects"]
                    phash = cpu["phash"]

                    comp = composite_score(aes, sharp, exp, face_count, weights)

                    # Duplicate detection
                    dup_of = _find_duplicate(phash, phash_cache, settings.max_phash_distance)
                    if not dup_of:
                        phash_cache[phash] = img_id

                    await session.execute(
                        update(ImageORM).where(ImageORM.id == img_id).values(
                            width=cpu["width"],
                            height=cpu["height"],
                            captured_at=cpu["captured_at"],
                            phash=phash,
                            face_rects=json.dumps(face_rects),
                            aesthetic_score=round(aes, 3),
                            sharpness_score=round(sharp, 3),
                            exposure_score=round(exp, 3),
                            face_count=face_count,
                            composite_score=round(comp, 4),
                            is_duplicate=dup_of is not None,
                            duplicate_of_id=dup_of,
                            status="scored",
                            scored_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        )
                    )

                # Mark failed images
                for fid in failed_ids:
                    await session.execute(
                        update(ImageORM).where(ImageORM.id == fid).values(
                            status="error", error_message="Failed to open or process image"
                        )
                    )

                await session.commit()

                # Update scan job scored_files counter (find active job for these paths)
                try:
                    from sqlalchemy import select
                    result = await session.execute(
                        select(ScanJob).where(ScanJob.status == "running").order_by(ScanJob.id.desc()).limit(1)
                    )
                    job = result.scalar_one_or_none()
                    if job:
                        await session.execute(
                            update(ScanJob)
                            .where(ScanJob.id == job.id)
                            .values(scored_files=ScanJob.scored_files + len(batch_items))
                        )
                        await session.commit()
                except Exception as e:
                    logger.warning("Could not update scan job counter: %s", e)

        # Signal queue items done
        for _ in batch_items:
            score_queue.task_done()

"""Print-ready JPEG export with smart crop and content-based renaming."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import piexif
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Album, AlbumImage, Image as ImageORM

# Print sizes at 300 DPI (width x height in pixels)
PRINT_SIZES: dict[str, tuple[int, int]] = {
    "4x6":      (1800, 1200),
    "5x7":      (2100, 1500),
    "8x10":     (3000, 2400),
    "a4_multi": (2480, 3508),
}

PRINT_SIZE_LABELS = {
    "4x6": "4×6 inches (standard)",
    "5x7": "5×7 inches",
    "8x10": "8×10 inches",
    "a4_multi": "A4 sheet (4 photos)",
}


def smart_crop(
    img: Image.Image,
    target_w: int,
    target_h: int,
    face_rects: list[list[int]] | None = None,
) -> Image.Image:
    """
    Scale image so its short side matches target, then crop to target dimensions.
    If face_rects provided, shift the crop window toward the face centroid.
    """
    src_w, src_h = img.size

    # Scale so the image fully covers the target (cover mode)
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Default center crop
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2

    # Face-aware crop: shift toward face centroid
    if face_rects:
        # Scale face rects to the resized dimensions
        face_cx_sum = sum((r[0] + r[2] / 2) * scale for r in face_rects)
        face_cy_sum = sum((r[1] + r[3] / 2) * scale for r in face_rects)
        n = len(face_rects)
        centroid_x = face_cx_sum / n
        centroid_y = face_cy_sum / n

        # Ideal crop window centered on face centroid, clamped to bounds
        left = int(max(0, min(new_w - target_w, centroid_x - target_w / 2)))
        top = int(max(0, min(new_h - target_h, centroid_y - target_h / 2)))

    return img.crop((left, top, left + target_w, top + target_h))


def _make_a4_grid(images: list[Image.Image], dpi: int = 300) -> Image.Image:
    """Tile up to 4 images in a 2×2 grid on an A4 canvas."""
    canvas_w, canvas_h = PRINT_SIZES["a4_multi"]
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    padding = 50
    cell_w = (canvas_w - padding * 3) // 2
    cell_h = (canvas_h - padding * 3) // 2

    positions = [
        (padding, padding),
        (padding * 2 + cell_w, padding),
        (padding, padding * 2 + cell_h),
        (padding * 2 + cell_w, padding * 2 + cell_h),
    ]
    for i, (img, pos) in enumerate(zip(images[:4], positions)):
        cell = smart_crop(img, cell_w, cell_h)
        canvas.paste(cell, pos)
    return canvas


def _set_dpi_exif(path: str, dpi: int) -> None:
    """Write DPI into the JPEG EXIF tags."""
    try:
        exif_dict = {"0th": {
            piexif.ImageIFD.XResolution: (dpi, 1),
            piexif.ImageIFD.YResolution: (dpi, 1),
            piexif.ImageIFD.ResolutionUnit: 2,  # inches
        }}
        exif_bytes = piexif.dump(exif_dict)
        img = Image.open(path)
        img.save(path, "JPEG", exif=exif_bytes, quality=95)
    except Exception:
        pass


def make_export_filename(image: ImageORM, sort_order: int, print_size: str) -> str:
    """
    Build a descriptive filename from EXIF date + scene slug.
    e.g. 2024-07-04_beach_sunset_0001_4x6.jpg
    """
    date_prefix = "unknown_date"
    if image.captured_at:
        date_prefix = image.captured_at.strftime("%Y-%m-%d")

    # Extract scene slug if we have it stored (set during scoring via a custom attr or filename scan)
    # We reuse the original filename's stem as fallback
    scene = Path(image.filename).stem.lower().replace(" ", "_")[:30]

    size_suffix = print_size.replace("x", "x")
    return f"{date_prefix}_{scene}_{sort_order:04d}_{size_suffix}.jpg"


async def export_album(
    album_id: int,
    output_dir: str,
    session: AsyncSession,
    dpi: int = 300,
) -> list[str]:
    """
    Export all album images as print-ready JPEGs with smart crop.
    Returns list of exported file paths.
    """
    result = await session.execute(
        select(AlbumImage)
        .where(AlbumImage.album_id == album_id)
        .order_by(AlbumImage.sort_order)
    )
    album_images = result.scalars().all()

    if not album_images:
        return []

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    exported: list[str] = []

    # Group a4_multi images in sets of 4
    a4_buffer: list[tuple[Image.Image, AlbumImage]] = []
    a4_group_start = 1

    for idx, ai in enumerate(album_images, start=1):
        img_row: ImageORM = (
            await session.execute(select(ImageORM).where(ImageORM.id == ai.image_id))
        ).scalar_one()

        try:
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                pass
            pil_img = Image.open(img_row.path).convert("RGB")
        except Exception as e:
            continue

        face_rects = None
        if img_row.face_rects:
            try:
                face_rects = json.loads(img_row.face_rects)
            except Exception:
                pass

        if ai.print_size == "a4_multi":
            a4_buffer.append((pil_img, ai))
            if len(a4_buffer) == 4 or idx == len(album_images):
                grid_img = _make_a4_grid([x[0] for x in a4_buffer])
                fname = f"a4_grid_{a4_group_start:04d}-{idx:04d}.jpg"
                dest = str(out_path / fname)
                grid_img.save(dest, "JPEG", quality=95)
                _set_dpi_exif(dest, dpi)
                exported.append(dest)
                a4_buffer = []
                a4_group_start = idx + 1
        else:
            target_w, target_h = PRINT_SIZES[ai.print_size]
            src_w, src_h = pil_img.size
            # Landscape images: keep landscape; portrait: keep portrait
            if src_w < src_h and target_w > target_h:
                target_w, target_h = target_h, target_w

            cropped = smart_crop(pil_img, target_w, target_h, face_rects)
            fname = make_export_filename(img_row, idx, ai.print_size)
            dest = str(out_path / fname)
            cropped.save(dest, "JPEG", quality=95)
            _set_dpi_exif(dest, dpi)
            exported.append(dest)

    # Update album export metadata
    await session.execute(
        update(Album)
        .where(Album.id == album_id)
        .values(
            exported_at=datetime.now(timezone.utc).replace(tzinfo=None),
            export_path=str(out_path),
        )
    )
    await session.commit()
    return exported

"""Album management endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import Album, AlbumImage, Image as ImageORM, get_session

router = APIRouter(prefix="/api/albums", tags=["albums"])

VALID_PRINT_SIZES = {"4x6", "5x7", "8x10", "a4_multi"}


class AlbumCreate(BaseModel):
    name: str


class AlbumImageAdd(BaseModel):
    image_id: int
    print_size: str = "4x6"
    sort_order: int = 0


class AlbumImageUpdate(BaseModel):
    print_size: str | None = None
    sort_order: int | None = None


class AlbumImageSchema(BaseModel):
    id: int
    image_id: int
    print_size: str
    sort_order: int
    filename: str
    thumbnail_url: str
    composite_score: float | None

    model_config = {"from_attributes": True}


class AlbumSchema(BaseModel):
    id: int
    name: str
    created_at: datetime
    exported_at: datetime | None
    export_path: str | None
    image_count: int = 0


class AlbumDetail(AlbumSchema):
    images: list[AlbumImageSchema]


@router.post("", response_model=AlbumSchema)
async def create_album(req: AlbumCreate, session: AsyncSession = Depends(get_session)):
    album = Album(name=req.name, created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    session.add(album)
    await session.commit()
    await session.refresh(album)
    return AlbumSchema(id=album.id, name=album.name, created_at=album.created_at,
                       exported_at=None, export_path=None, image_count=0)


@router.get("", response_model=list[AlbumSchema])
async def list_albums(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Album).order_by(Album.created_at.desc()))
    albums = result.scalars().all()
    out = []
    for a in albums:
        count = (await session.execute(
            select(func.count()).select_from(AlbumImage).where(AlbumImage.album_id == a.id)
        )).scalar_one()
        out.append(AlbumSchema(id=a.id, name=a.name, created_at=a.created_at,
                               exported_at=a.exported_at, export_path=a.export_path,
                               image_count=count))
    return out


@router.get("/{album_id}", response_model=AlbumDetail)
async def get_album(album_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Album).where(Album.id == album_id).options(
            selectinload(Album.images).selectinload(AlbumImage.image)
        )
    )
    album = result.scalar_one_or_none()
    if not album:
        raise HTTPException(404, "Album not found")

    images = [
        AlbumImageSchema(
            id=ai.id,
            image_id=ai.image_id,
            print_size=ai.print_size,
            sort_order=ai.sort_order,
            filename=ai.image.filename,
            thumbnail_url=f"/api/images/{ai.image_id}/thumbnail",
            composite_score=ai.image.composite_score,
        )
        for ai in album.images
    ]
    return AlbumDetail(
        id=album.id, name=album.name, created_at=album.created_at,
        exported_at=album.exported_at, export_path=album.export_path,
        image_count=len(images), images=images,
    )


@router.post("/{album_id}/images", response_model=AlbumImageSchema)
async def add_image_to_album(
    album_id: int, req: AlbumImageAdd, session: AsyncSession = Depends(get_session)
):
    if req.print_size not in VALID_PRINT_SIZES:
        raise HTTPException(400, f"Invalid print_size. Options: {', '.join(VALID_PRINT_SIZES)}")

    # Verify album and image exist
    album = (await session.execute(select(Album).where(Album.id == album_id))).scalar_one_or_none()
    if not album:
        raise HTTPException(404, "Album not found")
    img = (await session.execute(select(ImageORM).where(ImageORM.id == req.image_id))).scalar_one_or_none()
    if not img:
        raise HTTPException(404, "Image not found")

    ai = AlbumImage(album_id=album_id, image_id=req.image_id,
                    print_size=req.print_size, sort_order=req.sort_order)
    session.add(ai)
    await session.commit()
    await session.refresh(ai)
    return AlbumImageSchema(
        id=ai.id, image_id=ai.image_id, print_size=ai.print_size, sort_order=ai.sort_order,
        filename=img.filename, thumbnail_url=f"/api/images/{img.id}/thumbnail",
        composite_score=img.composite_score,
    )


@router.patch("/{album_id}/images/{image_id}")
async def update_album_image(
    album_id: int, image_id: int, req: AlbumImageUpdate,
    session: AsyncSession = Depends(get_session),
):
    values = {}
    if req.print_size is not None:
        if req.print_size not in VALID_PRINT_SIZES:
            raise HTTPException(400, "Invalid print_size")
        values["print_size"] = req.print_size
    if req.sort_order is not None:
        values["sort_order"] = req.sort_order
    if not values:
        raise HTTPException(400, "Nothing to update")

    result = await session.execute(
        update(AlbumImage)
        .where(AlbumImage.album_id == album_id, AlbumImage.image_id == image_id)
        .values(**values)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Album image not found")
    await session.commit()
    return {"updated": True}


@router.delete("/{album_id}/images/{image_id}")
async def remove_from_album(
    album_id: int, image_id: int, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        delete(AlbumImage)
        .where(AlbumImage.album_id == album_id, AlbumImage.image_id == image_id)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Album image not found")
    await session.commit()
    return {"removed": True}


@router.delete("/{album_id}")
async def delete_album(album_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(delete(Album).where(Album.id == album_id))
    if result.rowcount == 0:
        raise HTTPException(404, "Album not found")
    await session.commit()
    return {"deleted": True}

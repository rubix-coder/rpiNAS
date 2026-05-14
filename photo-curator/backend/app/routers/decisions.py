"""Image decision endpoints: approve, reject, skip, bulk."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Image as ImageORM, get_session

router = APIRouter(prefix="/api/images", tags=["decisions"])

VALID_DECISIONS = {"approved", "rejected", "skipped", "undecided"}


class BulkDecideRequest(BaseModel):
    ids: list[int]
    decision: str


@router.post("/{image_id}/approve")
async def approve(image_id: int, session: AsyncSession = Depends(get_session)):
    return await _set_decision(image_id, "approved", session)


@router.post("/{image_id}/reject")
async def reject(image_id: int, session: AsyncSession = Depends(get_session)):
    return await _set_decision(image_id, "rejected", session)


@router.post("/{image_id}/skip")
async def skip(image_id: int, session: AsyncSession = Depends(get_session)):
    return await _set_decision(image_id, "skipped", session)


@router.post("/{image_id}/undecide")
async def undecide(image_id: int, session: AsyncSession = Depends(get_session)):
    return await _set_decision(image_id, "undecided", session)


@router.post("/bulk-decide")
async def bulk_decide(req: BulkDecideRequest, session: AsyncSession = Depends(get_session)):
    if req.decision not in VALID_DECISIONS:
        raise HTTPException(400, f"Invalid decision. Must be one of: {', '.join(VALID_DECISIONS)}")
    result = await session.execute(
        update(ImageORM).where(ImageORM.id.in_(req.ids)).values(decision=req.decision)
    )
    await session.commit()
    return {"updated": result.rowcount}


async def _set_decision(image_id: int, decision: str, session: AsyncSession):
    result = await session.execute(
        update(ImageORM).where(ImageORM.id == image_id).values(decision=decision)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Image not found")
    await session.commit()
    return {"id": image_id, "decision": decision}

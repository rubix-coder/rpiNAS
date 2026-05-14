"""App settings persistence and path testing."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AppSetting, get_session
from ..services.scan_service import test_path_access

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_SETTINGS = {
    "last_image_dir": "",
    "last_export_dir": "",
    "path_type": "local",
}


@router.get("")
async def get_settings_api(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AppSetting))
    rows = result.scalars().all()
    data = dict(DEFAULT_SETTINGS)
    data.update({r.key: r.value for r in rows})

    # Enrich with system default if nothing saved yet
    if not data["last_image_dir"]:
        from ..config import get_settings
        data["last_image_dir"] = get_settings().image_dir
    return data


class SettingsUpdate(BaseModel):
    last_image_dir: str | None = None
    last_export_dir: str | None = None
    path_type: str | None = None


@router.patch("")
async def update_settings(req: SettingsUpdate, session: AsyncSession = Depends(get_session)):
    updates = req.model_dump(exclude_none=True)
    for key, value in updates.items():
        existing = (await session.execute(
            select(AppSetting).where(AppSetting.key == key)
        )).scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            session.add(AppSetting(key=key, value=value))
    await session.commit()
    return {"updated": list(updates.keys())}


class PathTestRequest(BaseModel):
    path: str


@router.post("/test-path")
async def test_path(req: PathTestRequest):
    result = test_path_access(req.path)
    if result["accessible"]:
        count = result["file_count"]
        msg = f"Great! Found {count:,} photo{'s' if count != 1 else ''} in this folder."
        return {"accessible": True, "file_count": count, "message": msg}
    else:
        return {"accessible": False, "file_count": 0, "message": result["error"]}


@router.get("/print-sizes")
async def get_print_sizes():
    from ..services.export_service import PRINT_SIZE_LABELS
    return PRINT_SIZE_LABELS

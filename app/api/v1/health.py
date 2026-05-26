from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """サーバとDBの疎通確認"""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:  # noqa: BLE001
        db_status = f"error: {e}"
    return {"status": "ok", "db": db_status}

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

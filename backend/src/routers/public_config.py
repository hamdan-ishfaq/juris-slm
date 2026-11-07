"""Public branding config — Phase 10D."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from config import settings

router = APIRouter(prefix="/api/v1/config", tags=["config"])


class BrandingResponse(BaseModel):
    brand_name: str
    brand_tagline: str
    brand_logo_url: str
    brand_primary_color: str


@router.get("/branding", response_model=BrandingResponse)
async def get_branding():
    return BrandingResponse(
        brand_name=settings.brand_name,
        brand_tagline=settings.brand_tagline,
        brand_logo_url=settings.brand_logo_url,
        brand_primary_color=settings.brand_primary_color,
    )

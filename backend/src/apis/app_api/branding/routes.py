"""Public branding endpoint — no authentication required."""
import logging
from fastapi import APIRouter, HTTPException, status

from apis.app_api.admin.branding.models import BrandingConfigResponse
from apis.app_api.admin.branding import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/branding", tags=["branding"])


@router.get("", response_model=BrandingConfigResponse)
async def get_public_branding():
    """
    Return the current branding configuration.

    Public endpoint — no authentication required.  Called by the SPA at startup
    so the login page and pre-auth screens use the correct brand colors and logos.
    """
    try:
        return await service.get_branding_response()
    except Exception:
        logger.exception("Error fetching public branding config")
        # Degrade gracefully — return empty config so defaults apply
        return BrandingConfigResponse()
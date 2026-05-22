"""Admin branding endpoints — require system administrator access."""
import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from apis.shared.auth.models import User
from apis.shared.rbac.system_admin import require_system_admin
from .models import BrandingConfigResponse, UpdateBrandingRequest, LogoPresignRequest, LogoPresignResponse
from . import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/branding", tags=["admin-branding"])


@router.get("", response_model=BrandingConfigResponse)
async def get_branding(admin: User = Depends(require_system_admin)):
    """Return current branding configuration with fresh presigned asset URLs."""
    try:
        return await service.get_branding_response()
    except Exception:
        logger.exception("Error fetching branding config")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching branding config")


@router.put("", response_model=BrandingConfigResponse)
async def update_branding(req: UpdateBrandingRequest, admin: User = Depends(require_system_admin)):
    """Update brand colors and/or logo S3 keys. Partial updates are supported."""
    try:
        return await service.update_branding(req, updated_by=admin.email)
    except Exception:
        logger.exception("Error updating branding config")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating branding config")


@router.post("/presign-logo", response_model=LogoPresignResponse, status_code=status.HTTP_201_CREATED)
async def presign_logo(req: LogoPresignRequest, admin: User = Depends(require_system_admin)):
    """Get a presigned PUT URL to upload a logo or favicon directly to S3."""
    try:
        return await service.presign_logo_upload(req)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception("Error generating presigned URL")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error generating presigned URL")


@router.post("/upload-logo", response_model=BrandingConfigResponse, status_code=status.HTTP_201_CREATED)
async def upload_logo(
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    admin: User = Depends(require_system_admin),
):
    """Upload a logo or favicon via multipart form. The file is stored in S3 server-side,
    which avoids any S3 CORS requirement on the browser side."""
    try:
        file_bytes = await file.read()
        return await service.upload_logo_asset(
            asset_type=asset_type,
            file_bytes=file_bytes,
            content_type=file.content_type or "application/octet-stream",
            filename=file.filename or "upload",
            updated_by=admin.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception("Error uploading logo asset")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error uploading logo asset")
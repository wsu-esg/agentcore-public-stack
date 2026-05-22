"""Service layer for branding configuration."""
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
import boto3

from .models import (
    BrandingConfig, BrandingConfigResponse, BrandingColors,
    LogoPresignRequest, LogoPresignResponse, UpdateBrandingRequest,
)
from . import repository

logger = logging.getLogger(__name__)

ALLOWED_ASSET_TYPES = {"logo_light", "logo_dark", "favicon"}
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/x-icon", "image/webp"}
_PRESIGN_TTL = 3600          # 1 hour for upload presigned URLs
_GET_URL_TTL = 900           # 15 min for display presigned GET URLs


def _s3_client():
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    return boto3.client("s3", region_name=region)


def _bucket_name() -> str:
    name = os.environ.get("S3_USER_FILES_BUCKET_NAME", "")
    if not name:
        raise RuntimeError("S3_USER_FILES_BUCKET_NAME is not set")
    return name


def _presigned_get_url(s3_key: str) -> str:
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket_name(), "Key": s3_key},
        ExpiresIn=_GET_URL_TTL,
    )


async def get_branding_response() -> BrandingConfigResponse:
    config = await repository.get_branding()
    if config is None:
        return BrandingConfigResponse()
    return BrandingConfigResponse(
        colors=config.colors,
        logo_light_url=_presigned_get_url(config.logo_light_s3_key) if config.logo_light_s3_key else None,
        logo_dark_url=_presigned_get_url(config.logo_dark_s3_key) if config.logo_dark_s3_key else None,
        favicon_url=_presigned_get_url(config.favicon_s3_key) if config.favicon_s3_key else None,
        updated_at=config.updated_at,
        updated_by=config.updated_by,
    )


async def update_branding(req: UpdateBrandingRequest, updated_by: str) -> BrandingConfigResponse:
    existing = await repository.get_branding() or BrandingConfig()
    if req.colors is not None:
        existing.colors = req.colors
    if req.logo_light_s3_key is not None:
        existing.logo_light_s3_key = req.logo_light_s3_key
    if req.logo_dark_s3_key is not None:
        existing.logo_dark_s3_key = req.logo_dark_s3_key
    if req.favicon_s3_key is not None:
        existing.favicon_s3_key = req.favicon_s3_key
    existing.updated_at = datetime.now(timezone.utc).isoformat()
    existing.updated_by = updated_by
    await repository.save_branding(existing)
    return await get_branding_response()


async def presign_logo_upload(req: LogoPresignRequest) -> LogoPresignResponse:
    if req.asset_type not in ALLOWED_ASSET_TYPES:
        raise ValueError(f"asset_type must be one of {ALLOWED_ASSET_TYPES}")
    if req.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"content_type must be one of {ALLOWED_CONTENT_TYPES}")
    ext = req.filename.rsplit(".", 1)[-1] if "." in req.filename else "bin"
    s3_key = f"branding/{req.asset_type}/{uuid.uuid4()}.{ext}"
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=_PRESIGN_TTL)).isoformat()
    url = _s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket_name(), "Key": s3_key, "ContentType": req.content_type},
        ExpiresIn=_PRESIGN_TTL,
    )
    return LogoPresignResponse(presigned_url=url, s3_key=s3_key, expires_at=expires_at)


_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB — enough for any logo or favicon


async def upload_logo_asset(
    asset_type: str,
    file_bytes: bytes,
    content_type: str,
    filename: str,
    updated_by: str,
) -> BrandingConfigResponse:
    """Upload a logo or favicon directly to S3 and save the S3 key to branding config.

    Accepts the raw file bytes from the app-api multipart endpoint so the
    browser never talks to S3 directly, removing any S3 CORS requirement.
    """
    if asset_type not in ALLOWED_ASSET_TYPES:
        raise ValueError(f"asset_type must be one of {ALLOWED_ASSET_TYPES}")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"content_type must be one of {ALLOWED_CONTENT_TYPES}")
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise ValueError(f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")

    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    s3_key = f"branding/{asset_type}/{uuid.uuid4()}.{ext}"

    _s3_client().put_object(
        Bucket=_bucket_name(),
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )
    logger.info("Uploaded branding asset: %s (%s bytes)", s3_key, len(file_bytes))

    field = f"{asset_type}_s3_key"
    return await update_branding(UpdateBrandingRequest(**{field: s3_key}), updated_by=updated_by)
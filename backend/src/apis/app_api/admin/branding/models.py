"""Pydantic models for branding configuration."""
from pydantic import BaseModel, Field
from typing import Optional


class BrandingColors(BaseModel):
    primary: str = Field(description="Hex color for primary scale, e.g. #0033a0")
    secondary: str = Field(description="Hex color for secondary scale, e.g. #d64309")
    tertiary: str = Field(description="Hex color for tertiary scale, e.g. #0072ce")
    sidebar_bg: Optional[str] = Field(None, description="Sidebar/nav background in light mode, e.g. #f3f4f6")
    sidebar_bg_dark: Optional[str] = Field(None, description="Sidebar/nav background in dark mode, e.g. #111827")
    chat_bg: Optional[str] = Field(None, description="Chat frame background in light mode, e.g. #f9fafb")
    chat_bg_dark: Optional[str] = Field(None, description="Chat frame background in dark mode, e.g. #111827")


class BrandingConfig(BaseModel):
    colors: Optional[BrandingColors] = None
    logo_light_s3_key: Optional[str] = None   # S3 key in user-files bucket
    logo_dark_s3_key: Optional[str] = None
    favicon_s3_key: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class BrandingConfigResponse(BaseModel):
    """Returned by both public GET /branding and admin GET /admin/branding."""
    colors: Optional[BrandingColors] = None
    logo_light_url: Optional[str] = None   # Fresh presigned GET URL (15 min)
    logo_dark_url: Optional[str] = None
    favicon_url: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class UpdateBrandingRequest(BaseModel):
    colors: Optional[BrandingColors] = None
    logo_light_s3_key: Optional[str] = None
    logo_dark_s3_key: Optional[str] = None
    favicon_s3_key: Optional[str] = None


class LogoPresignRequest(BaseModel):
    asset_type: str = Field(description="One of: logo_light, logo_dark, favicon")
    content_type: str = Field(description="MIME type, e.g. image/png")
    filename: str


class LogoPresignResponse(BaseModel):
    presigned_url: str
    s3_key: str
    expires_at: str
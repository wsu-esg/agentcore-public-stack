"""DynamoDB repository for branding configuration."""
import logging
import os
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from .models import BrandingConfig, BrandingColors

logger = logging.getLogger(__name__)

_TABLE_NAME_ENV = "DYNAMODB_BRANDING_TABLE_NAME"
PK = "BRANDING"
SK = "GLOBAL"


def _table():
    table_name = os.environ.get(_TABLE_NAME_ENV, "")
    if not table_name:
        raise RuntimeError(f"{_TABLE_NAME_ENV} is not set")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    ddb = boto3.resource("dynamodb", region_name=region)
    return ddb.Table(table_name)


async def get_branding() -> Optional[BrandingConfig]:
    try:
        resp = _table().get_item(Key={"PK": PK, "SK": SK})
        item = resp.get("Item")
        if not item:
            return None
        colors = None
        if item.get("primary_color"):
            colors = BrandingColors(
                primary=item["primary_color"],
                secondary=item.get("secondary_color", "#d64309"),
                tertiary=item.get("tertiary_color", "#0072ce"),
                sidebar_bg=item.get("sidebar_bg") or None,
                sidebar_bg_dark=item.get("sidebar_bg_dark") or None,
                chat_bg=item.get("chat_bg") or None,
                chat_bg_dark=item.get("chat_bg_dark") or None,
                text_primary=item.get("text_primary") or None,
                text_primary_dark=item.get("text_primary_dark") or None,
                text_muted=item.get("text_muted") or None,
                text_muted_dark=item.get("text_muted_dark") or None,
                chat_input_bg=item.get("chat_input_bg") or None,
                chat_input_bg_dark=item.get("chat_input_bg_dark") or None,
            )
        return BrandingConfig(
            colors=colors,
            logo_light_s3_key=item.get("logo_light_s3_key"),
            logo_dark_s3_key=item.get("logo_dark_s3_key"),
            favicon_s3_key=item.get("favicon_s3_key"),
            updated_at=item.get("updated_at"),
            updated_by=item.get("updated_by"),
        )
    except RuntimeError:
        # Table not configured (local dev / test environment) — degrade gracefully.
        logger.debug("Branding table not configured; returning empty config")
        return None
    except ClientError:
        logger.exception("DynamoDB error fetching branding config")
        return None


async def save_branding(config: BrandingConfig) -> None:
    item = {"PK": PK, "SK": SK}
    if config.colors:
        item["primary_color"] = config.colors.primary
        item["secondary_color"] = config.colors.secondary
        item["tertiary_color"] = config.colors.tertiary
        if config.colors.sidebar_bg is not None:
            item["sidebar_bg"] = config.colors.sidebar_bg
        if config.colors.sidebar_bg_dark is not None:
            item["sidebar_bg_dark"] = config.colors.sidebar_bg_dark
        if config.colors.chat_bg is not None:
            item["chat_bg"] = config.colors.chat_bg
        if config.colors.chat_bg_dark is not None:
            item["chat_bg_dark"] = config.colors.chat_bg_dark
        if config.colors.text_primary is not None:
            item["text_primary"] = config.colors.text_primary
        if config.colors.text_primary_dark is not None:
            item["text_primary_dark"] = config.colors.text_primary_dark
        if config.colors.text_muted is not None:
            item["text_muted"] = config.colors.text_muted
        if config.colors.text_muted_dark is not None:
            item["text_muted_dark"] = config.colors.text_muted_dark
        if config.colors.chat_input_bg is not None:
            item["chat_input_bg"] = config.colors.chat_input_bg
        if config.colors.chat_input_bg_dark is not None:
            item["chat_input_bg_dark"] = config.colors.chat_input_bg_dark
    if config.logo_light_s3_key is not None:
        item["logo_light_s3_key"] = config.logo_light_s3_key
    if config.logo_dark_s3_key is not None:
        item["logo_dark_s3_key"] = config.logo_dark_s3_key
    if config.favicon_s3_key is not None:
        item["favicon_s3_key"] = config.favicon_s3_key
    if config.updated_at:
        item["updated_at"] = config.updated_at
    if config.updated_by:
        item["updated_by"] = config.updated_by
    _table().put_item(Item=item)
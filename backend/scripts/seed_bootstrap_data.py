#!/usr/bin/env python3
"""
Bootstrap data seeding script for first-time platform deployment.

Seeds auth providers, quota tiers, quota assignments, and Bedrock models
into DynamoDB and Secrets Manager. Designed to be invoked by
scripts/stack-bootstrap/seed.sh after infrastructure deployment.

All operations are idempotent: re-running with identical inputs produces
the same database state.

Environment variables:
    DDB_AUTH_PROVIDERS_TABLE  - Auth providers DynamoDB table name
    DDB_USER_QUOTAS_TABLE     - User quotas DynamoDB table name
    DDB_MANAGED_MODELS_TABLE  - Managed models DynamoDB table name
    SECRETS_AUTH_ARN          - Secrets Manager ARN for auth secrets
    AWS_REGION                - AWS region

    SEED_AUTH_PROVIDER_ID     - Provider slug (e.g., entra-id)
    SEED_AUTH_DISPLAY_NAME    - Login page display name
    SEED_AUTH_ISSUER_URL      - OIDC issuer URL
    SEED_AUTH_CLIENT_ID       - OAuth client ID
    SEED_AUTH_CLIENT_SECRET   - OAuth client secret
    SEED_AUTH_BUTTON_COLOR    - Hex color for login button (optional)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
import httpx
from botocore.exceptions import ClientError

logger = logging.getLogger("seed_bootstrap_data")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Fixed namespace for deterministic model UUIDs
MODEL_UUID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


@dataclass
class SeedResult:
    """Result of a single seed operation."""

    category: str
    created: int = 0
    skipped: int = 0
    failed: int = 0
    details: list[str] = field(default_factory=list)


def seed_auth_provider(
    table_name: str,
    secrets_arn: str,
    region: str,
    provider_id: str,
    display_name: str,
    issuer_url: str,
    client_id: str,
    client_secret: str,
    button_color: str | None = None,
    discover: bool = True,
) -> SeedResult:
    """Seed a single OIDC auth provider into DynamoDB and Secrets Manager."""
    result = SeedResult(category="auth_provider")
    session = boto3.Session(region_name=region)
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(table_name)
    secrets_client = session.client("secretsmanager")

    pk = f"AUTH_PROVIDER#{provider_id}"

    # Check for existing item
    try:
        existing = table.get_item(Key={"PK": pk, "SK": pk})
        if "Item" in existing:
            msg = f"Auth provider '{provider_id}' already exists — skipped"
            logger.info(msg)
            result.skipped = 1
            result.details.append(msg)
            return result
    except ClientError as e:
        msg = f"Failed to check existing auth provider '{provider_id}': {e}"
        logger.error(msg)
        result.failed = 1
        result.details.append(msg)
        return result

    # OIDC discovery
    discovered: dict[str, Any] = {}
    if discover:
        discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
        logger.info("Discovering OIDC endpoints from %s", discovery_url)
        try:
            resp = httpx.get(discovery_url, timeout=10.0, follow_redirects=True)
            resp.raise_for_status()
            discovered = resp.json()
            logger.info("OIDC discovery successful")
        except Exception as e:
            logger.warning("OIDC discovery failed: %s — continuing without discovered endpoints", e)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    item: dict[str, Any] = {
        "PK": pk,
        "SK": pk,
        "GSI1PK": "ENABLED#true",
        "GSI1SK": pk,
        "providerId": provider_id,
        "displayName": display_name,
        "providerType": "oidc",
        "enabled": True,
        "issuerUrl": issuer_url,
        "clientId": client_id,
        "scopes": "openid profile email",
        "responseType": "code",
        "pkceEnabled": True,
        "userIdClaim": "sub",
        "emailClaim": "email",
        "nameClaim": "name",
        "rolesClaim": "roles",
        "pictureClaim": "picture",
        "firstNameClaim": "given_name",
        "lastNameClaim": "family_name",
        "createdAt": now,
        "updatedAt": now,
        "createdBy": "bootstrap-seed",
    }

    # Map discovered endpoints
    endpoint_mapping = {
        "authorizationEndpoint": "authorization_endpoint",
        "tokenEndpoint": "token_endpoint",
        "jwksUri": "jwks_uri",
        "userinfoEndpoint": "userinfo_endpoint",
        "endSessionEndpoint": "end_session_endpoint",
    }
    for dynamo_key, oidc_key in endpoint_mapping.items():
        value = discovered.get(oidc_key)
        if value:
            item[dynamo_key] = value

    if button_color:
        item["buttonColor"] = button_color

    # Write to DynamoDB
    try:
        table.put_item(Item=item)
        logger.info("Auth provider '%s' written to DynamoDB", provider_id)
    except ClientError as e:
        msg = f"Failed to write auth provider '{provider_id}' to DynamoDB: {e}"
        logger.error(msg)
        result.failed = 1
        result.details.append(msg)
        return result

    # Write client secret to Secrets Manager
    try:
        try:
            response = secrets_client.get_secret_value(SecretId=secrets_arn)
            secrets = json.loads(response["SecretString"])
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                secrets = {}
            else:
                raise
        except (json.JSONDecodeError, KeyError):
            secrets = {}

        if provider_id not in secrets:
            secrets[provider_id] = client_secret
            secrets_client.put_secret_value(
                SecretId=secrets_arn,
                SecretString=json.dumps(secrets),
            )
            logger.info("Client secret for '%s' stored in Secrets Manager", provider_id)
        else:
            logger.info("Client secret for '%s' already in Secrets Manager — kept existing", provider_id)
    except ClientError as e:
        msg = f"Failed to write secret for '{provider_id}': {e}"
        logger.error(msg)
        result.failed = 1
        result.details.append(msg)
        return result

    result.created = 1
    result.details.append(f"Auth provider '{provider_id}' created")
    return result


def seed_default_quota_tier(
    table_name: str,
    region: str,
) -> SeedResult:
    """Seed the default quota tier ($50 monthly, 80% soft limit, block)."""
    result = SeedResult(category="quota_tier")
    session = boto3.Session(region_name=region)
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(table_name)

    pk = "QUOTA_TIER#default"
    sk = "METADATA"

    try:
        existing = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" in existing:
            msg = "Default quota tier already exists — skipped"
            logger.info(msg)
            result.skipped = 1
            result.details.append(msg)
            return result
    except ClientError as e:
        msg = f"Failed to check existing quota tier: {e}"
        logger.error(msg)
        result.failed = 1
        result.details.append(msg)
        return result

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    item = {
        "PK": pk,
        "SK": sk,
        "tierId": "default",
        "tierName": "Default Tier",
        "description": "Default quota tier for all users",
        "monthlyCostLimit": Decimal("50.00"),
        "periodType": "monthly",
        "softLimitPercentage": Decimal("80.0"),
        "actionOnLimit": "block",
        "enabled": True,
        "createdAt": now,
        "updatedAt": now,
        "createdBy": "bootstrap-seed",
    }

    try:
        table.put_item(Item=item)
        logger.info("Default quota tier created")
        result.created = 1
        result.details.append("Default quota tier created")
    except ClientError as e:
        msg = f"Failed to write default quota tier: {e}"
        logger.error(msg)
        result.failed = 1
        result.details.append(msg)

    return result


def seed_default_quota_assignment(
    table_name: str,
    region: str,
    tier_id: str = "default",
) -> SeedResult:
    """Seed the default quota assignment (default_tier type, priority 100)."""
    result = SeedResult(category="quota_assignment")
    session = boto3.Session(region_name=region)
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(table_name)

    pk = "ASSIGNMENT#default-assignment"
    sk = "METADATA"

    try:
        existing = table.get_item(Key={"PK": pk, "SK": sk})
        if "Item" in existing:
            msg = "Default quota assignment already exists — skipped"
            logger.info(msg)
            result.skipped = 1
            result.details.append(msg)
            return result
    except ClientError as e:
        msg = f"Failed to check existing quota assignment: {e}"
        logger.error(msg)
        result.failed = 1
        result.details.append(msg)
        return result

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    item = {
        "PK": pk,
        "SK": sk,
        "GSI1PK": "ASSIGNMENT_TYPE#default_tier",
        "GSI1SK": "PRIORITY#100#default-assignment",
        "assignmentId": "default-assignment",
        "tierId": tier_id,
        "assignmentType": "default_tier",
        "priority": 100,
        "enabled": True,
        "createdAt": now,
        "updatedAt": now,
        "createdBy": "bootstrap-seed",
    }

    try:
        table.put_item(Item=item)
        logger.info("Default quota assignment created")
        result.created = 1
        result.details.append("Default quota assignment created")
    except ClientError as e:
        msg = f"Failed to write default quota assignment: {e}"
        logger.error(msg)
        result.failed = 1
        result.details.append(msg)

    return result


# Default Bedrock models to seed
DEFAULT_MODELS: list[dict[str, Any]] = [
    {
        "modelId": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "modelName": "Claude Haiku 4.5",
        "provider": "bedrock",
        "providerName": "Amazon Bedrock",
        "inputModalities": ["text", "image"],
        "outputModalities": ["text"],
        "maxInputTokens": 200000,
        "maxOutputTokens": 64000,
        "inputPricePerMillionTokens": Decimal("1.00"),
        "outputPricePerMillionTokens": Decimal("5.00"),
        "cacheWritePricePerMillionTokens": Decimal("1.25"),
        "cacheReadPricePerMillionTokens": Decimal("0.10"),
        "isReasoningModel": False,
        "supportsCaching": True,
        "isDefault": True,
    },
    {
        "modelId": "us.anthropic.claude-sonnet-4-6",
        "modelName": "Claude Sonnet 4.6",
        "provider": "bedrock",
        "providerName": "Amazon Bedrock",
        "inputModalities": ["text", "image"],
        "outputModalities": ["text"],
        "maxInputTokens": 200000,
        "maxOutputTokens": 64000,
        "inputPricePerMillionTokens": Decimal("3.00"),
        "outputPricePerMillionTokens": Decimal("15.00"),
        "cacheWritePricePerMillionTokens": Decimal("3.75"),
        "cacheReadPricePerMillionTokens": Decimal("0.30"),
        "isReasoningModel": False,
        "supportsCaching": True,
        "isDefault": False,
    },
]


def seed_default_models(
    table_name: str,
    region: str,
) -> SeedResult:
    """Seed default Bedrock model registrations."""
    result = SeedResult(category="model")
    session = boto3.Session(region_name=region)
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(table_name)

    for model_def in DEFAULT_MODELS:
        model_id = model_def["modelId"]
        deterministic_uuid = str(uuid.uuid5(MODEL_UUID_NAMESPACE, model_id))

        # Check existence via GSI query
        try:
            query_resp = table.query(
                IndexName="ModelIdIndex",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("GSI1PK").eq(f"MODEL#{model_id}"),
                Limit=1,
            )
            if query_resp.get("Items"):
                msg = f"Model '{model_def['modelName']}' ({model_id}) already exists — skipped"
                logger.info(msg)
                result.skipped += 1
                result.details.append(msg)
                continue
        except ClientError as e:
            msg = f"Failed to check existing model '{model_id}': {e}"
            logger.error(msg)
            result.failed += 1
            result.details.append(msg)
            continue

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        pk = f"MODEL#{deterministic_uuid}"
        item: dict[str, Any] = {
            "PK": pk,
            "SK": pk,
            "GSI1PK": f"MODEL#{model_id}",
            "GSI1SK": pk,
            "id": deterministic_uuid,
            "modelId": model_id,
            "modelName": model_def["modelName"],
            "provider": model_def["provider"],
            "providerName": model_def["providerName"],
            "inputModalities": model_def["inputModalities"],
            "outputModalities": model_def["outputModalities"],
            "maxInputTokens": model_def["maxInputTokens"],
            "maxOutputTokens": model_def["maxOutputTokens"],
            "allowedAppRoles": [],
            "availableToRoles": [],
            "enabled": True,
            "inputPricePerMillionTokens": model_def["inputPricePerMillionTokens"],
            "outputPricePerMillionTokens": model_def["outputPricePerMillionTokens"],
            "cacheWritePricePerMillionTokens": model_def["cacheWritePricePerMillionTokens"],
            "cacheReadPricePerMillionTokens": model_def["cacheReadPricePerMillionTokens"],
            "isReasoningModel": model_def["isReasoningModel"],
            "supportsCaching": model_def["supportsCaching"],
            "isDefault": model_def["isDefault"],
            "createdAt": now,
            "updatedAt": now,
        }

        try:
            table.put_item(Item=item)
            msg = f"Model '{model_def['modelName']}' ({model_id}) created"
            logger.info(msg)
            result.created += 1
            result.details.append(msg)
        except ClientError as e:
            msg = f"Failed to write model '{model_id}': {e}"
            logger.error(msg)
            result.failed += 1
            result.details.append(msg)

    return result


def print_summary(results: list[SeedResult]) -> None:
    """Print a structured summary of all seed operations."""
    print()
    print("=" * 60)
    print("  Bootstrap Data Seeding Summary")
    print("=" * 60)
    for r in results:
        print(f"  {r.category:<20s}  created={r.created}  skipped={r.skipped}  failed={r.failed}")
        for detail in r.details:
            print(f"    - {detail}")
    print("=" * 60)

    total_failed = sum(r.failed for r in results)
    if total_failed:
        print(f"  RESULT: {total_failed} operation(s) failed")
    else:
        total_created = sum(r.created for r in results)
        total_skipped = sum(r.skipped for r in results)
        print(f"  RESULT: OK ({total_created} created, {total_skipped} skipped)")
    print()


def main() -> None:
    """Entry point: read env vars, dispatch seeders, print summary."""
    # Required env vars for DynamoDB tables and region
    auth_table = os.environ.get("DDB_AUTH_PROVIDERS_TABLE", "")
    quotas_table = os.environ.get("DDB_USER_QUOTAS_TABLE", "")
    models_table = os.environ.get("DDB_MANAGED_MODELS_TABLE", "")
    secrets_arn = os.environ.get("SECRETS_AUTH_ARN", "")
    region = os.environ.get("AWS_REGION", "us-east-1")

    # Auth provider env vars (all optional — skip seeding if any missing)
    auth_provider_id = os.environ.get("SEED_AUTH_PROVIDER_ID", "")
    auth_display_name = os.environ.get("SEED_AUTH_DISPLAY_NAME", "")
    auth_issuer_url = os.environ.get("SEED_AUTH_ISSUER_URL", "")
    auth_client_id = os.environ.get("SEED_AUTH_CLIENT_ID", "")
    auth_client_secret = os.environ.get("SEED_AUTH_CLIENT_SECRET", "")
    auth_button_color = os.environ.get("SEED_AUTH_BUTTON_COLOR", "") or None

    results: list[SeedResult] = []

    # --- Auth provider seeding ---
    required_auth_vars = {
        "SEED_AUTH_ISSUER_URL": auth_issuer_url,
        "SEED_AUTH_CLIENT_ID": auth_client_id,
        "SEED_AUTH_CLIENT_SECRET": auth_client_secret,
    }
    missing_auth = [k for k, v in required_auth_vars.items() if not v]

    if missing_auth:
        logger.warning(
            "Skipping auth provider seeding — missing env vars: %s",
            ", ".join(missing_auth),
        )
        result = SeedResult(category="auth_provider", skipped=1)
        result.details.append(f"Skipped — missing: {', '.join(missing_auth)}")
        results.append(result)
    else:
        results.append(
            seed_auth_provider(
                table_name=auth_table,
                secrets_arn=secrets_arn,
                region=region,
                provider_id=auth_provider_id or "default",
                display_name=auth_display_name or "Default Provider",
                issuer_url=auth_issuer_url,
                client_id=auth_client_id,
                client_secret=auth_client_secret,
                button_color=auth_button_color,
                discover=True,
            )
        )

    # --- Quota tier seeding ---
    results.append(seed_default_quota_tier(table_name=quotas_table, region=region))

    # --- Quota assignment seeding ---
    results.append(
        seed_default_quota_assignment(table_name=quotas_table, region=region, tier_id="default")
    )

    # --- Model seeding ---
    results.append(seed_default_models(table_name=models_table, region=region))

    # --- Summary ---
    print_summary(results)

    total_failed = sum(r.failed for r in results)
    sys.exit(1 if total_failed else 0)


if __name__ == "__main__":
    main()

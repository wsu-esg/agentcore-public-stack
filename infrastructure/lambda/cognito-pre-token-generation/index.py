import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> dict:
    trigger_source = event.get("triggerSource", "")
    user_attributes = event.get("request", {}).get("userAttributes", {})

    logger.info(f"Pre-token trigger: {trigger_source}")

    custom_roles_raw = user_attributes.get("custom:roles", "")

    if custom_roles_raw:
        logger.info(f"Injecting custom:roles into token: {custom_roles_raw}")
        event.setdefault("response", {})
        event["response"]["claimsAndScopeOverrideDetails"] = {
            "idTokenGeneration": {
                "claimsToAddOrOverride": {
                    "custom:roles": custom_roles_raw,
                }
            }
        }
    else:
        logger.info("No custom:roles found on user profile — skipping injection")

    return event
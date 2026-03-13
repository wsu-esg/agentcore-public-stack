"""Tests for handle_modify (MODIFY/update runtime flow)."""

import os
import sys

import pytest
from botocore.exceptions import ClientError

_tests_dir = os.path.dirname(__file__)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from conftest import make_modify_event, AUTH_PROVIDERS_TABLE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_provider(mod, pid, runtime_id="test-runtime-id"):
    """Insert a provider record so DynamoDB status updates succeed."""
    mod.dynamodb.put_item(
        TableName=AUTH_PROVIDERS_TABLE,
        Item={
            "PK": {"S": f"AUTH_PROVIDER#{pid}"},
            "SK": {"S": f"AUTH_PROVIDER#{pid}"},
            "providerId": {"S": pid},
            "agentcoreRuntimeId": {"S": runtime_id},
            "agentcoreRuntimeStatus": {"S": "CREATING"},
        },
    )


def _get_provider(mod, pid):
    """Read back the provider record from DynamoDB."""
    resp = mod.dynamodb.get_item(
        TableName=AUTH_PROVIDERS_TABLE,
        Key={
            "PK": {"S": f"AUTH_PROVIDER#{pid}"},
            "SK": {"S": f"AUTH_PROVIDER#{pid}"},
        },
    )
    return resp.get("Item", {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestModifyDetectsChanges:
    """Verify that changes to each JWT field trigger an update."""

    def test_modify_detects_issuer_url_change(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-issuer"
        _seed_provider(mod, pid)

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        bedrock.update_agent_runtime.assert_called_once()

    def test_modify_detects_client_id_change(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-client"
        _seed_provider(mod, pid)

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://same.example.com",
            new_issuer_url="https://same.example.com",
            old_client_id="old-client",
            new_client_id="new-client",
        )
        mod.lambda_handler(event, {})

        bedrock.update_agent_runtime.assert_called_once()

    def test_modify_detects_jwks_uri_change(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-jwks"
        _seed_provider(mod, pid)

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://same.example.com",
            new_issuer_url="https://same.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
            old_jwks_uri="https://old.example.com/.well-known/jwks.json",
            new_jwks_uri="https://new.example.com/.well-known/jwks.json",
        )
        mod.lambda_handler(event, {})

        bedrock.update_agent_runtime.assert_called_once()


class TestModifyNoOp:
    """No bedrock call when JWT fields are unchanged."""

    def test_modify_noop_when_jwt_unchanged(self, lambda_module):
        mod, bedrock = lambda_module

        event = make_modify_event(
            provider_id="prov-noop",
            old_issuer_url="https://same.example.com",
            new_issuer_url="https://same.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        bedrock.update_agent_runtime.assert_not_called()


class TestModifyUpdateDetails:
    """Validate what gets sent to bedrock on update."""

    def test_modify_updates_authorizer_config(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-auth"
        _seed_provider(mod, pid)

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="old-client",
            new_client_id="new-client",
        )
        mod.lambda_handler(event, {})

        call_kwargs = bedrock.update_agent_runtime.call_args[1]
        auth_cfg = call_kwargs["authorizerConfiguration"]["customJWTAuthorizer"]

        assert "new.example.com" in auth_cfg["discoveryUrl"]
        assert auth_cfg["allowedAudience"] == ["new-client"]

    def test_modify_preserves_existing_config(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-preserve"
        _seed_provider(mod, pid)

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="old-client",
            new_client_id="new-client",
        )
        mod.lambda_handler(event, {})

        call_kwargs = bedrock.update_agent_runtime.call_args[1]

        # Container artifact preserved from get_agent_runtime mock
        assert call_kwargs["agentRuntimeArtifact"] == {
            "containerConfiguration": {
                "containerUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo:latest",
            }
        }
        # Network config preserved
        assert call_kwargs["networkConfiguration"] == {"networkMode": "PUBLIC"}
        # Role ARN preserved
        assert call_kwargs["roleArn"] == "arn:aws:iam::123456789012:role/test-runtime-role"


class TestModifyDynamoDBStatus:
    """DynamoDB status updates after modify."""

    def test_modify_updates_dynamodb_status_ready(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-ready"
        _seed_provider(mod, pid)

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        item = _get_provider(mod, pid)
        assert item["agentcoreRuntimeStatus"]["S"] == "READY"


class TestModifyEdgeCases:
    """Edge cases: missing runtime ID, bedrock failure."""

    def test_modify_missing_runtime_id_skips(self, lambda_module):
        mod, bedrock = lambda_module

        # Build event without agentcoreRuntimeId in NewImage
        event = make_modify_event(
            provider_id="prov-noid",
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
            runtime_id="",  # will produce empty string
        )
        # Remove the runtime id key entirely from NewImage
        del event["Records"][0]["dynamodb"]["NewImage"]["agentcoreRuntimeId"]
        del event["Records"][0]["dynamodb"]["OldImage"]["agentcoreRuntimeId"]

        mod.lambda_handler(event, {})

        bedrock.update_agent_runtime.assert_not_called()

    def test_modify_failure_sets_update_failed(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-fail"
        _seed_provider(mod, pid)

        bedrock.update_agent_runtime.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "bad config"}},
            "UpdateAgentRuntime",
        )

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        item = _get_provider(mod, pid)
        assert item["agentcoreRuntimeStatus"]["S"] == "UPDATE_FAILED"
        assert "agentcoreRuntimeError" in item


class TestModifyPreservesEnvironmentVariables:
    """Environment variables must survive JWT config updates."""

    def test_modify_preserves_env_vars(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-envvars"
        _seed_provider(mod, pid)

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        call_kwargs = bedrock.update_agent_runtime.call_args[1]
        assert call_kwargs["environmentVariables"] == {
            "TABLE_NAME": "my-table",
            "API_KEY": "secret-123",
        }

    def test_modify_works_when_no_env_vars_exist(self, lambda_module):
        """If the runtime has no env vars, update should still succeed
        without passing environmentVariables."""
        mod, bedrock = lambda_module
        pid = "prov-noenv"
        _seed_provider(mod, pid)

        # Override mock to return a runtime with no env vars
        runtime_resp = bedrock.get_agent_runtime.return_value.copy()
        del runtime_resp["environmentVariables"]
        bedrock.get_agent_runtime.return_value = runtime_resp

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        call_kwargs = bedrock.update_agent_runtime.call_args[1]
        assert "environmentVariables" not in call_kwargs


class TestModifyAlwaysIncludesAuthorizationHeader:
    """Authorization header must always be in the allowlist."""

    def test_modify_always_includes_authorization(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-auth-hdr"
        _seed_provider(mod, pid)

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        call_kwargs = bedrock.update_agent_runtime.call_args[1]
        allowlist = call_kwargs["requestHeaderConfiguration"]["requestHeaderAllowlist"]
        assert "Authorization" in allowlist

    def test_modify_includes_authorization_even_when_field_missing(self, lambda_module):
        """If get_agent_runtime omits requestHeaderConfiguration entirely,
        Authorization must still be set."""
        mod, bedrock = lambda_module
        pid = "prov-no-hdr"
        _seed_provider(mod, pid)

        # Override mock to return a runtime with no header config
        runtime_resp = bedrock.get_agent_runtime.return_value.copy()
        del runtime_resp["requestHeaderConfiguration"]
        bedrock.get_agent_runtime.return_value = runtime_resp

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        call_kwargs = bedrock.update_agent_runtime.call_args[1]
        allowlist = call_kwargs["requestHeaderConfiguration"]["requestHeaderAllowlist"]
        assert "Authorization" in allowlist

    def test_modify_preserves_custom_headers(self, lambda_module):
        mod, bedrock = lambda_module
        pid = "prov-custom-hdr"
        _seed_provider(mod, pid)

        # Override mock to include a custom header alongside Authorization
        runtime_resp = bedrock.get_agent_runtime.return_value.copy()
        runtime_resp["requestHeaderConfiguration"] = {
            "requestHeaderAllowlist": [
                "Authorization",
                "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Trace-Id",
            ]
        }
        bedrock.get_agent_runtime.return_value = runtime_resp

        event = make_modify_event(
            provider_id=pid,
            old_issuer_url="https://old.example.com",
            new_issuer_url="https://new.example.com",
            old_client_id="same-client",
            new_client_id="same-client",
        )
        mod.lambda_handler(event, {})

        call_kwargs = bedrock.update_agent_runtime.call_args[1]
        allowlist = call_kwargs["requestHeaderConfiguration"]["requestHeaderAllowlist"]
        assert "Authorization" in allowlist
        assert "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Trace-Id" in allowlist

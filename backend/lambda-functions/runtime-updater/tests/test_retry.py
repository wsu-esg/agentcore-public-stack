"""Tests for retry logic, backoff, and error classification (update_runtime_with_retry)."""

import sys
import os
from unittest.mock import patch, MagicMock, call

from botocore.exceptions import ClientError

_tests_dir = os.path.dirname(__file__)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from conftest import make_provider_record, AUTH_PROVIDERS_TABLE


def _make_client_error(code, message="test error"):
    return ClientError(
        {"Error": {"Code": code, "Message": message}}, "UpdateAgentRuntime"
    )


def _success_runtime_response():
    return {
        "roleArn": "arn:aws:iam::123456789012:role/test-runtime-role",
        "networkConfiguration": {"networkMode": "PUBLIC"},
        "agentRuntimeArtifact": {
            "containerConfiguration": {"containerUri": "old-repo:v1"}
        },
        "authorizerConfiguration": {
            "customJWTAuthorizer": {
                "discoveryUrl": "https://example.com/.well-known/openid-configuration",
                "allowedAudience": ["aud"],
                "allowedClients": ["client"],
            }
        },
        "environmentVariables": {"KEY": "value"},
    }


_PROVIDER = {"provider_id": "p1", "runtime_id": "rt-1", "display_name": "Provider 1"}


def _seed(lambda_module):
    make_provider_record(
        lambda_module.dynamodb, "p1", runtime_id="rt-1"
    )


def _get_db_status(lambda_module, provider_id="p1"):
    resp = lambda_module.dynamodb.get_item(
        TableName=AUTH_PROVIDERS_TABLE,
        Key={
            "PK": {"S": f"AUTH_PROVIDER#{provider_id}"},
            "SK": {"S": f"AUTH_PROVIDER#{provider_id}"},
        },
    )
    return resp["Item"]


class TestRetryLogic:

    def test_success_on_first_attempt(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.return_value = (
            _success_runtime_response()
        )
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep"):
            result = lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        assert result["success"] is True
        assert result["attempts"] == 1

    def test_throttling_retries(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = [
            _make_client_error("ThrottlingException"),
            _make_client_error("ThrottlingException"),
            _success_runtime_response(),
        ]
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep") as mock_sleep:
            result = lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        assert result["success"] is True
        assert result["attempts"] == 3
        mock_sleep.assert_any_call(2)   # 2^1
        mock_sleep.assert_any_call(4)   # 2^2

    def test_service_unavailable_retries(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = [
            _make_client_error("ServiceUnavailableException"),
            _success_runtime_response(),
        ]
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep") as mock_sleep:
            result = lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        assert result["success"] is True
        assert result["attempts"] == 2
        mock_sleep.assert_called_once_with(2)  # 2^1

    def test_resource_not_found_fails_immediately(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = _make_client_error(
            "ResourceNotFoundException"
        )

        with patch("lambda_function.time.sleep") as mock_sleep:
            result = lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        assert result["success"] is False
        assert result["attempts"] == 1
        mock_sleep.assert_not_called()

    def test_validation_exception_fails_immediately(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = _make_client_error(
            "ValidationException"
        )

        with patch("lambda_function.time.sleep") as mock_sleep:
            result = lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        assert result["success"] is False
        assert result["attempts"] == 1
        mock_sleep.assert_not_called()

    def test_exponential_backoff_timing(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = [
            _make_client_error("ThrottlingException"),
            _make_client_error("ThrottlingException"),
            _success_runtime_response(),
        ]
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep") as mock_sleep:
            lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        assert mock_sleep.call_args_list == [call(2), call(4)]

    def test_max_retries_exhausted(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = [
            _make_client_error("ThrottlingException"),
            _make_client_error("ThrottlingException"),
            _make_client_error("ThrottlingException"),
        ]

        with patch("lambda_function.time.sleep"):
            result = lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        assert result["success"] is False
        assert result["attempts"] == 3

    def test_status_transitions_updating_then_ready(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.return_value = (
            _success_runtime_response()
        )
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep"):
            lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        item = _get_db_status(lambda_module)
        assert item["agentcoreRuntimeStatus"]["S"] == "READY"

    def test_status_transitions_updating_then_failed(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = _make_client_error(
            "ResourceNotFoundException", "not found"
        )

        with patch("lambda_function.time.sleep"):
            lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        item = _get_db_status(lambda_module)
        assert item["agentcoreRuntimeStatus"]["S"] == "UPDATE_FAILED"

    def test_non_client_error_retries(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = [
            RuntimeError("transient"),
            _success_runtime_response(),
        ]
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep") as mock_sleep:
            result = lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        assert result["success"] is True
        assert result["attempts"] == 2
        mock_sleep.assert_called_once_with(2)

    def test_error_message_in_dynamodb(self, lambda_module):
        _seed(lambda_module)
        lambda_module.bedrock_agentcore.get_agent_runtime.side_effect = _make_client_error(
            "ResourceNotFoundException", "Runtime rt-1 does not exist"
        )

        with patch("lambda_function.time.sleep"):
            lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        item = _get_db_status(lambda_module)
        assert item["agentcoreRuntimeStatus"]["S"] == "UPDATE_FAILED"
        assert "rt-1 does not exist" in item["agentcoreRuntimeError"]["S"]

    def test_update_preserves_runtime_config(self, lambda_module):
        _seed(lambda_module)
        runtime_resp = _success_runtime_response()
        lambda_module.bedrock_agentcore.get_agent_runtime.return_value = runtime_resp
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep"):
            lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        lambda_module.bedrock_agentcore.update_agent_runtime.assert_called_once()
        call_kwargs = lambda_module.bedrock_agentcore.update_agent_runtime.call_args[1]

        assert call_kwargs["agentRuntimeId"] == "rt-1"
        assert call_kwargs["agentRuntimeArtifact"] == {
            "containerConfiguration": {"containerUri": "repo:v2.0.0"}
        }
        assert call_kwargs["roleArn"] == runtime_resp["roleArn"]
        assert call_kwargs["networkConfiguration"] == runtime_resp["networkConfiguration"]
        assert call_kwargs["authorizerConfiguration"] == runtime_resp["authorizerConfiguration"]
        assert call_kwargs["environmentVariables"] == runtime_resp["environmentVariables"]

    def test_update_always_includes_authorization_header(self, lambda_module):
        """Authorization header MUST be in requestHeaderAllowlist even when
        the current runtime has NO requestHeaderConfiguration at all."""
        _seed(lambda_module)
        runtime_resp = _success_runtime_response()
        # Simulate the field being absent from GetAgentRuntime response
        runtime_resp.pop("requestHeaderConfiguration", None)
        lambda_module.bedrock_agentcore.get_agent_runtime.return_value = runtime_resp
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep"):
            lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        call_kwargs = lambda_module.bedrock_agentcore.update_agent_runtime.call_args[1]
        header_cfg = call_kwargs["requestHeaderConfiguration"]
        assert "Authorization" in header_cfg["requestHeaderAllowlist"]

    def test_update_preserves_custom_headers_alongside_authorization(self, lambda_module):
        """Existing custom headers must be preserved, and Authorization must
        still be present even if it wasn't in the original allowlist."""
        _seed(lambda_module)
        runtime_resp = _success_runtime_response()
        runtime_resp["requestHeaderConfiguration"] = {
            "requestHeaderAllowlist": [
                "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Trace-Id"
            ]
        }
        lambda_module.bedrock_agentcore.get_agent_runtime.return_value = runtime_resp
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep"):
            lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        call_kwargs = lambda_module.bedrock_agentcore.update_agent_runtime.call_args[1]
        allowlist = call_kwargs["requestHeaderConfiguration"]["requestHeaderAllowlist"]
        assert "Authorization" in allowlist
        assert "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Trace-Id" in allowlist

    def test_update_does_not_duplicate_authorization_header(self, lambda_module):
        """If Authorization is already in the allowlist, it should not appear twice."""
        _seed(lambda_module)
        runtime_resp = _success_runtime_response()
        runtime_resp["requestHeaderConfiguration"] = {
            "requestHeaderAllowlist": ["Authorization"]
        }
        lambda_module.bedrock_agentcore.get_agent_runtime.return_value = runtime_resp
        lambda_module.bedrock_agentcore.update_agent_runtime.return_value = {}

        with patch("lambda_function.time.sleep"):
            lambda_module.update_runtime_with_retry(_PROVIDER, "repo:v2.0.0")

        call_kwargs = lambda_module.bedrock_agentcore.update_agent_runtime.call_args[1]
        allowlist = call_kwargs["requestHeaderConfiguration"]["requestHeaderAllowlist"]
        assert allowlist.count("Authorization") == 1

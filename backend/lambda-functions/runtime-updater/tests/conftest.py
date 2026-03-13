"""
Test fixtures for the runtime-updater Lambda function.

Handles the tricky module-level boto3 client creation by:
1. Setting env vars before any import
2. Using moto's mock_aws for DynamoDB, SSM, and SNS
3. Patching boto3.client to intercept 'bedrock-agentcore-control' (unsupported by moto)
4. Importing/reloading lambda_function inside the fixture
5. Replacing module-level client references after reload
"""

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_PREFIX = "test-project"
AWS_REGION = "us-east-1"
AUTH_PROVIDERS_TABLE = "test-auth-providers"
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:test-runtime-update-alerts"

# ---------------------------------------------------------------------------
# A. Environment variables — autouse so every test gets them
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    """Inject required environment variables before lambda_function is loaded."""
    monkeypatch.setenv("PROJECT_PREFIX", PROJECT_PREFIX)
    monkeypatch.setenv("AWS_REGION", AWS_REGION)
    monkeypatch.setenv("AWS_DEFAULT_REGION", AWS_REGION)
    monkeypatch.setenv("AUTH_PROVIDERS_TABLE", AUTH_PROVIDERS_TABLE)
    monkeypatch.setenv("SNS_TOPIC_ARN", SNS_TOPIC_ARN)
    # Dummy credentials for moto
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


# ---------------------------------------------------------------------------
# B. Mock bedrock-agentcore-control client
# ---------------------------------------------------------------------------

def _make_mock_bedrock_client():
    """Return a MagicMock that simulates the bedrock-agentcore-control client."""
    mock_client = MagicMock(name="bedrock-agentcore-control")

    mock_client.get_agent_runtime.return_value = {
        "agentRuntimeId": "rt-123",
        "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/rt-123",
        "roleArn": "arn:aws:iam::123456789012:role/test-runtime-role",
        "networkConfiguration": {
            "networkMode": "PUBLIC",
        },
        "agentRuntimeArtifact": {
            "containerConfiguration": {
                "containerUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo:v0.9.0",
            }
        },
        "authorizerConfiguration": {
            "customJWTAuthorizer": {
                "discoveryUrl": "https://example.com/.well-known/openid-configuration",
                "allowedAudience": ["test-audience"],
                "allowedClients": ["test-client-id"],
            }
        },
        "environmentVariables": {
            "ENV_VAR_1": "value1",
            "ENV_VAR_2": "value2",
        },
        "status": "READY",
    }
    mock_client.update_agent_runtime.return_value = {}

    return mock_client


@pytest.fixture()
def mock_bedrock_client():
    """Expose the mock bedrock-agentcore-control client for direct assertions."""
    return _make_mock_bedrock_client()


# ---------------------------------------------------------------------------
# C–E. lambda_module fixture (the "reload dance")
# ---------------------------------------------------------------------------

@pytest.fixture()
def lambda_module(mock_bedrock_client):
    """
    Import (or reload) lambda_function inside moto's mock_aws context so that
    the module-level boto3 clients point at moto fakes for DynamoDB/SSM/SNS and
    a MagicMock for bedrock-agentcore-control.

    Returns the module object so tests can call e.g.
        result = lambda_module.lambda_handler(event, {})

    Also creates the DynamoDB table, SSM parameters, and SNS topic that the
    Lambda expects.
    """
    with mock_aws():
        real_boto3_client = boto3.client

        def _patched_client(service_name, *args, **kwargs):
            if service_name == "bedrock-agentcore-control":
                return mock_bedrock_client
            return real_boto3_client(service_name, *args, **kwargs)

        with patch("boto3.client", side_effect=_patched_client):
            # Prevent the Lambda from running pip install at import time
            with patch("pip._internal.main", return_value=None):
                # Remove cached module so it re-executes top-level code
                module_key = "lambda_function"
                sys.modules.pop(module_key, None)

                # Ensure the Lambda directory is on sys.path for bare imports
                lambda_dir = os.path.join(
                    os.path.dirname(__file__), os.pardir
                )
                lambda_dir = os.path.normpath(lambda_dir)
                if lambda_dir not in sys.path:
                    sys.path.insert(0, lambda_dir)

                import lambda_function  # noqa: E402

                # --- Create AWS resources inside moto ---

                # C. DynamoDB table
                ddb = boto3.client("dynamodb", region_name=AWS_REGION)
                ddb.create_table(
                    TableName=AUTH_PROVIDERS_TABLE,
                    KeySchema=[
                        {"AttributeName": "PK", "KeyType": "HASH"},
                        {"AttributeName": "SK", "KeyType": "RANGE"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "PK", "AttributeType": "S"},
                        {"AttributeName": "SK", "AttributeType": "S"},
                    ],
                    BillingMode="PAY_PER_REQUEST",
                )

                # D. SSM parameters
                ssm = boto3.client("ssm", region_name=AWS_REGION)
                ssm.put_parameter(
                    Name=f"/{PROJECT_PREFIX}/inference-api/image-tag",
                    Value="v1.0.0",
                    Type="String",
                )
                ssm.put_parameter(
                    Name=f"/{PROJECT_PREFIX}/inference-api/ecr-repository-uri",
                    Value="123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo",
                    Type="String",
                )

                # E. SNS topic
                sns = boto3.client("sns", region_name=AWS_REGION)
                sns.create_topic(Name="test-runtime-update-alerts")

                # Replace module-level client references with our moto/mock clients
                lambda_function.dynamodb = ddb
                lambda_function.ssm = ssm
                lambda_function.ecr = boto3.client("ecr", region_name=AWS_REGION)
                lambda_function.bedrock_agentcore = mock_bedrock_client
                lambda_function.sns = sns

                yield lambda_function

        # Clean up sys.modules to avoid cross-test pollution
        sys.modules.pop("lambda_function", None)


# ---------------------------------------------------------------------------
# F. Convenience fixtures that pull from lambda_module
# ---------------------------------------------------------------------------

@pytest.fixture()
def dynamodb_client(lambda_module):
    """Return the moto-backed DynamoDB client used by the Lambda module."""
    return lambda_module.dynamodb


@pytest.fixture()
def ssm_client(lambda_module):
    """Return the moto-backed SSM client used by the Lambda module."""
    return lambda_module.ssm


@pytest.fixture()
def sns_client(lambda_module):
    """Return the moto-backed SNS client used by the Lambda module."""
    return lambda_module.sns


@pytest.fixture()
def bedrock_client(lambda_module):
    """Return the mock bedrock-agentcore-control client used by the Lambda module."""
    return lambda_module.bedrock_agentcore


# ---------------------------------------------------------------------------
# G. EventBridge event factory
# ---------------------------------------------------------------------------

def make_ssm_change_event(parameter_name=None, operation="Update"):
    """Create an EventBridge SSM Parameter Store Change event."""
    return {
        "source": "aws.ssm",
        "detail-type": "Parameter Store Change",
        "detail": {
            "name": parameter_name
            or f"/{PROJECT_PREFIX}/inference-api/image-tag",
            "operation": operation,
        },
    }


# ---------------------------------------------------------------------------
# H. Provider record factory
# ---------------------------------------------------------------------------

def make_provider_record(
    dynamodb_client,
    provider_id,
    runtime_id="rt-123",
    runtime_arn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/rt-123",
    status="READY",
    display_name=None,
):
    """Create a provider DynamoDB item and insert it into the moto table.

    Args:
        dynamodb_client: The moto-backed DynamoDB client (from the fixture).
        provider_id: Unique provider identifier.
        runtime_id: AgentCore runtime ID.
        runtime_arn: AgentCore runtime ARN.
        status: Runtime status (READY, UPDATING, FAILED, etc.).
        display_name: Human-readable name; defaults to "Provider {provider_id}".

    Returns:
        The item dict (raw DynamoDB format) that was inserted.
    """
    item = {
        "PK": {"S": f"AUTH_PROVIDER#{provider_id}"},
        "SK": {"S": f"AUTH_PROVIDER#{provider_id}"},
        "providerId": {"S": provider_id},
        "agentcoreRuntimeId": {"S": runtime_id},
        "agentcoreRuntimeArn": {"S": runtime_arn},
        "agentcoreRuntimeStatus": {"S": status},
        "displayName": {"S": display_name or f"Provider {provider_id}"},
    }

    dynamodb_client.put_item(
        TableName=AUTH_PROVIDERS_TABLE,
        Item=item,
    )

    return item


# ---------------------------------------------------------------------------
# Tip: patching time.sleep for retry tests
# ---------------------------------------------------------------------------
# Use unittest.mock.patch on the module reference:
#     with patch.object(lambda_module, 'time', wraps=time) as mock_time:
#         mock_time.sleep = MagicMock()
#         ...
# Or more directly:
#     with patch('lambda_function.time.sleep'):
#         ...
#
# ---------------------------------------------------------------------------
# Tip: importing factory helpers in test files
# ---------------------------------------------------------------------------
# Because pyproject.toml uses --import-mode=importlib, bare `from conftest`
# imports don't work automatically.  In each test file add:
#
#     import sys, os
#     _tests_dir = os.path.dirname(__file__)
#     if _tests_dir not in sys.path:
#         sys.path.insert(0, _tests_dir)
#     from conftest import make_provider_record, make_ssm_change_event

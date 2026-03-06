# Runtime Provisioner Lambda

Automatically provisions, updates, and deletes AWS Bedrock AgentCore Runtimes based on DynamoDB Stream events from the Auth Providers table.

## Overview

This Lambda function implements the multi-runtime architecture for OIDC authentication providers. When an admin adds, updates, or deletes an authentication provider via the UI, this function automatically manages the corresponding AgentCore Runtime.

## Event Flow

- **INSERT**: Create new runtime with provider's JWT authorizer configuration
- **MODIFY**: Update runtime if JWT-relevant fields changed (issuer URL, client ID, JWKS URI)
- **REMOVE**: Delete runtime and clean up SSM parameters

## Environment Variables

Required environment variables:

- `PROJECT_PREFIX`: Project prefix for resource naming (e.g., "bsu")
- `AWS_REGION`: AWS region (e.g., "us-east-1")
- `AUTH_PROVIDERS_TABLE`: DynamoDB table name for auth providers

## IAM Permissions Required

The Lambda execution role needs the following permissions:

### DynamoDB
- `dynamodb:GetRecords` - Read stream events
- `dynamodb:GetShardIterator` - Process stream
- `dynamodb:DescribeStream` - Stream metadata
- `dynamodb:ListStreams` - List streams
- `dynamodb:UpdateItem` - Update provider runtime status

### Bedrock AgentCore
- `bedrock-agentcore:CreateAgentRuntime` - Create new runtimes
- `bedrock-agentcore:UpdateAgentRuntime` - Update existing runtimes
- `bedrock-agentcore:DeleteAgentRuntime` - Delete runtimes
- `bedrock-agentcore:GetAgentRuntime` - Fetch runtime configuration

### SSM Parameter Store
- `ssm:GetParameter` - Read configuration parameters
- `ssm:PutParameter` - Store runtime ARNs
- `ssm:DeleteParameter` - Clean up runtime ARNs

### ECR
- `ecr:DescribeRepositories` - Get repository details
- `ecr:DescribeImages` - Get image details

### IAM
- `iam:PassRole` - Pass runtime execution role to AgentCore

### CloudWatch Logs
- `logs:CreateLogGroup` - Create log groups
- `logs:CreateLogStream` - Create log streams
- `logs:PutLogEvents` - Write logs

## SSM Parameters Used

### Read Parameters
- `/${PROJECT_PREFIX}/inference-api/image-tag` - Container image tag
- `/${PROJECT_PREFIX}/inference-api/ecr-repository-uri` - ECR repository URI
- `/${PROJECT_PREFIX}/inference-api/runtime-execution-role-arn` - Runtime IAM role ARN

### Write Parameters
- `/${PROJECT_PREFIX}/runtimes/{provider_id}/arn` - Runtime ARN for each provider

## Runtime Creation Process

1. Extract provider details from DynamoDB Stream event
2. Fetch current container image tag from SSM
3. Construct runtime name: `{projectPrefix}_agentcore_runtime_{provider_id}`
4. Determine OIDC discovery URL from issuer URL
5. Call `CreateAgentRuntime` API with:
   - Container image URI from ECR
   - JWT authorizer config (discovery URL, allowed audience)
   - Runtime execution role ARN
   - Network configuration (PUBLIC mode)
   - Environment variables (project prefix, region, provider ID)
6. Store runtime ARN, ID, and endpoint URL in DynamoDB
7. Store runtime ARN in SSM for cross-stack reference

## Runtime Update Process

1. Check if JWT-relevant fields changed (issuer URL, client ID, JWKS URI)
2. If no changes, skip update
3. Fetch current runtime configuration via `GetAgentRuntime`
4. Call `UpdateAgentRuntime` with new JWT authorizer config
5. Preserve all other settings (container image, network, role)
6. Update DynamoDB status to READY

## Runtime Deletion Process

1. Extract runtime ID from DynamoDB Stream event
2. Call `DeleteAgentRuntime` API
3. Delete runtime ARN from SSM Parameter Store
4. Handle ResourceNotFoundException gracefully (already deleted)

## Error Handling

All exceptions during runtime operations are caught and handled:

1. Log detailed error information to CloudWatch
2. Update DynamoDB with FAILED status and error message
3. Don't re-raise exception (let DynamoDB Streams retry logic handle it)

## Retry Logic

Retry logic is handled by Lambda DynamoDB Stream integration:
- 3 automatic retry attempts
- Exponential backoff between retries
- Failed records sent to DLQ (if configured)

## Runtime Naming Convention

Runtime names follow the pattern: `{projectPrefix}_agentcore_runtime_{provider_id}`

Rules:
- Replace hyphens with underscores (AgentCore requirement)
- Use provider ID from database
- Include project prefix for multi-tenant isolation

Examples:
- `bsu_agentcore_runtime_entra_id`
- `bsu_agentcore_runtime_okta_prod`
- `bsu_agentcore_runtime_google_workspace`

## Runtime Endpoint URL

The runtime endpoint URL is constructed as:
```
https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{runtime_arn}/invocations
```

This URL is stored in DynamoDB and used by the frontend to route requests to the correct runtime.

## DynamoDB Updates

The function updates the following fields in the Auth Providers table:

- `agentcoreRuntimeArn` - Runtime ARN
- `agentcoreRuntimeId` - Runtime ID
- `agentcoreRuntimeEndpointUrl` - Runtime endpoint URL
- `agentcoreRuntimeStatus` - Status (PENDING, CREATING, READY, UPDATING, FAILED, UPDATE_FAILED)
- `agentcoreRuntimeError` - Error message (if failed)
- `updatedAt` - Timestamp

## Monitoring

CloudWatch Logs:
- All operations logged with INFO level
- Errors logged with ERROR level and stack traces
- Runtime creation/update/deletion events logged

CloudWatch Metrics (custom):
- Runtime creation success/failure count
- Runtime update success/failure count
- Runtime deletion success/failure count

## Testing

Local testing with sample DynamoDB Stream events:

```python
# Sample INSERT event
{
    "Records": [{
        "eventName": "INSERT",
        "dynamodb": {
            "NewImage": {
                "providerId": {"S": "test-provider"},
                "issuerUrl": {"S": "https://login.microsoftonline.com/tenant-id/v2.0"},
                "clientId": {"S": "client-id-123"},
                "jwksUri": {"S": "https://login.microsoftonline.com/tenant-id/discovery/v2.0/keys"}
            }
        }
    }]
}
```

## Deployment

This Lambda function is deployed via the RuntimeProvisionerStack CDK stack:

1. Package Lambda code and dependencies
2. Create Lambda function resource
3. Configure DynamoDB Stream event source
4. Set environment variables
5. Attach IAM role with required permissions
6. Configure CloudWatch log group with retention

## Dependencies

- `boto3==1.35.93` - AWS SDK for Python

## Related Documentation

- [Multi-Runtime Authentication Providers Design](../../../.kiro/specs/multi-runtime-auth-providers/design.md)
- [Multi-Runtime Authentication Providers Requirements](../../../.kiro/specs/multi-runtime-auth-providers/requirements.md)
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)

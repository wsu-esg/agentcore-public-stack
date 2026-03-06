# Runtime Updater Lambda

Automatically updates all AgentCore provider runtimes when new container images are deployed.

## Overview

This Lambda function is triggered by EventBridge when the SSM parameter for the inference API image tag changes. It queries all providers with existing runtimes and updates them in parallel with the new container image.

## Trigger

- **EventBridge Rule**: Detects changes to `/${PROJECT_PREFIX}/inference-api/image-tag` SSM parameter
- **Event Type**: SSM Parameter Store change notification

## Functionality

### Core Features

1. **Parallel Updates**: Updates up to 5 runtimes concurrently to minimize total update time
2. **Retry Logic**: Retries failed updates up to 3 times with exponential backoff (2s, 4s, 8s)
3. **Status Tracking**: Updates DynamoDB with runtime status (UPDATING, READY, UPDATE_FAILED)
4. **SNS Notifications**: Sends summary notifications with success/failure counts
5. **Error Isolation**: Individual runtime failures don't affect other updates

### Update Process

1. Extract new image tag from EventBridge event
2. Query DynamoDB for all providers with existing runtimes
3. Fetch new container image URI from ECR
4. Update runtimes in parallel (max 5 concurrent):
   - Fetch current runtime configuration via `GetAgentRuntime`
   - Call `UpdateAgentRuntime` with new container image
   - Preserve all other configuration (JWT auth, network, environment)
   - Retry up to 3 times with exponential backoff
5. Update DynamoDB status for each provider
6. Send SNS notification summary

## Environment Variables

- `PROJECT_PREFIX`: Project prefix for resource naming
- `AWS_REGION`: AWS region
- `AUTH_PROVIDERS_TABLE`: DynamoDB table name for auth providers
- `SNS_TOPIC_ARN`: SNS topic ARN for alerts

## IAM Permissions Required

- `bedrock-agentcore:GetAgentRuntime`
- `bedrock-agentcore:UpdateAgentRuntime`
- `dynamodb:Scan` (Auth Providers table)
- `dynamodb:UpdateItem` (Auth Providers table)
- `ssm:GetParameter` (image tag and ECR repository URI)
- `ecr:DescribeRepositories`
- `ecr:DescribeImages`
- `sns:Publish` (for alerts)

## Configuration

- **Max Concurrent Updates**: 5 runtimes at a time
- **Max Retry Attempts**: 3 attempts per runtime
- **Retry Backoff**: Exponential (2s, 4s, 8s)
- **Timeout**: 15 minutes (for parallel updates)
- **Memory**: 512 MB

## Error Handling

### Retryable Errors
- `ThrottlingException`: API rate limiting
- `ServiceUnavailableException`: Temporary service issues

### Non-Retryable Errors
- `ResourceNotFoundException`: Runtime not found (deleted externally)
- `ValidationException`: Invalid runtime configuration
- Other client errors

### Error Recovery
- Failed updates are marked in DynamoDB with `UPDATE_FAILED` status
- Error messages stored in `agentcoreRuntimeError` field
- SNS alerts sent for all failures
- Admin can retry manually via UI or wait for next image deployment

## SNS Notifications

### Update Summary
Sent after all updates complete:
```
Runtime Update Summary
======================

New Image Tag: v1.2.3
Total Runtimes: 5
Succeeded: 4
Failed: 1

Failed Updates:
--------------------------------------------------
Provider: Okta Production (okta-prod)
Error: ThrottlingException: Rate exceeded
Attempts: 3
```

### Critical Failure
Sent if Lambda encounters unrecoverable error:
```
Critical Failure in Runtime Updater Lambda

The Runtime Updater Lambda encountered a critical error and could not complete.

Error: [error message]

Action Required: Investigate Lambda logs and retry manually if needed.
```

## Monitoring

### CloudWatch Logs
- All update attempts logged with provider ID and attempt number
- Success/failure status for each runtime
- Detailed error messages for failures

### CloudWatch Metrics
Custom metrics published to `AgentCore/RuntimeUpdates` namespace:
- `UpdateSuccess`: Count of successful updates
- `UpdateFailure`: Count of failed updates
- `UpdateDuration`: Time taken to update all runtimes
- `RuntimeCount`: Total number of active runtimes

### CloudWatch Alarms
- **Runtime Update Failures**: Triggers when `UpdateFailure > 0`
- **High Update Duration**: Triggers when `UpdateDuration > 30 minutes`

## Testing

### Local Testing
```bash
# Set environment variables
export PROJECT_PREFIX=bsu
export AWS_REGION=us-east-1
export AUTH_PROVIDERS_TABLE=bsu-auth-providers
export SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:runtime-update-alerts

# Create test event
cat > test-event.json <<EOF
{
  "detail": {
    "name": "/bsu/inference-api/image-tag",
    "value": "v1.2.3"
  }
}
EOF

# Invoke Lambda locally
python lambda_function.py
```

### Integration Testing
1. Push new Docker image to ECR with new tag
2. Update SSM parameter: `/${PROJECT_PREFIX}/inference-api/image-tag`
3. Verify EventBridge triggers Lambda
4. Check CloudWatch logs for update progress
5. Verify DynamoDB status updated for all providers
6. Verify SNS notification received

## Deployment

Deployed as part of the App API Stack:
- Lambda function resource
- EventBridge rule for SSM parameter changes
- SNS topic for alerts
- IAM role with required permissions
- CloudWatch log group with retention policy

## Troubleshooting

### Lambda Timeout
- Increase timeout setting (default: 15 minutes)
- Reduce `MAX_CONCURRENT_UPDATES` to avoid API rate limits

### All Updates Failing
- Check Bedrock AgentCore API quotas
- Verify IAM permissions
- Check ECR image exists and is accessible

### Partial Failures
- Check CloudWatch logs for specific error messages
- Verify runtime still exists (not deleted externally)
- Check network connectivity

### SNS Notifications Not Received
- Verify SNS topic ARN is correct
- Check SNS topic subscriptions
- Verify Lambda has `sns:Publish` permission

## Future Enhancements

1. **Blue-Green Deployment**: Zero-downtime updates with traffic shifting
2. **Canary Updates**: Update subset of runtimes first, then roll out to all
3. **Rollback Support**: Automatic rollback on high failure rate
4. **Health Checks**: Verify runtime health after update before marking as READY
5. **Update Scheduling**: Schedule updates during low-usage periods

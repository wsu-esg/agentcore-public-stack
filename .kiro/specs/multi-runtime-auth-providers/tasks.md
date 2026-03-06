# Multi-Runtime Authentication Providers - Tasks

## Overview

This task list implements dynamic multi-runtime deployment for OIDC authentication providers. When an admin adds a provider via the UI, a Lambda function (integrated into the App API stack) automatically provisions a dedicated AWS Bedrock AgentCore Runtime with that provider's JWT authorizer configuration.

The Lambda functions for runtime management are deployed as part of the App API stack rather than a separate stack, avoiding unnecessary cross-stack dependencies since the App API stack already depends on the Inference API stack for shared resource ARNs.

## Task Breakdown

### Phase 1: Database Schema Updates

- [x] 2. Update Auth Providers DynamoDB Table
  - [x] 2.1 Add runtime tracking fields to AuthProvider model in backend
    - Add `agentcoreRuntimeArn: Optional[str]`
    - Add `agentcoreRuntimeId: Optional[str]`
    - Add `agentcoreRuntimeEndpointUrl: Optional[str]`
    - Add `agentcoreRuntimeStatus: str` (default: "PENDING")
    - Add `agentcoreRuntimeError: Optional[str]`
  - [x] 2.2 Enable DynamoDB Streams on Auth Providers table in AppApiStack
    - Set `stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES`
  - [x] 2.3 Export stream ARN to SSM Parameter Store
    - Parameter: `/${projectPrefix}/auth/auth-providers-stream-arn`
  - [x] 2.4 Deploy AppApiStack with schema changes

### Phase 2: Remove CDK-Managed Runtime

- [x] 3. Update InferenceApiStack
  - [x] 3.1 Remove runtime creation code
    - Remove `this.runtime = new bedrock.CfnRuntime(...)`
    - Remove runtime-specific SSM parameters
    - Remove runtime endpoint URL exports
  - [x] 3.2 Keep shared resources
    - Keep Memory, Gateway, Code Interpreter, Browser
    - Keep all IAM roles (runtime execution role will be used by Lambda-created runtimes)
  - [x] 3.3 Export runtime execution role ARN to SSM
    - Parameter: `/${projectPrefix}/inference-api/runtime-execution-role-arn`
  - [x] 3.4 Export shared resource ARNs to SSM (if not already exported)
    - Memory ARN, Gateway ID, Code Interpreter ID, Browser ID
  - [x] 3.5 Update CloudFormation outputs (remove runtime-specific outputs)
  - [x] 3.6 Deploy InferenceApiStack (this will delete the old runtime)

### Phase 3: Runtime Provisioner Lambda

- [x] 4. Create Runtime Provisioner Lambda Function
  - [x] 4.1 Create Lambda function code (`backend/lambda-functions/runtime-provisioner/`)
    - Implement DynamoDB Stream event handler
    - Implement `handle_insert()` - create new runtime
    - Implement `handle_modify()` - update runtime if JWT config changed
    - Implement `handle_remove()` - delete runtime and clean up SSM
  - [x] 4.2 Implement runtime creation logic
    - Fetch container image tag from SSM
    - Construct runtime name: `{projectPrefix}_agentcore_runtime_{provider_id}`
    - Determine discovery URL from issuer URL or JWKS URI
    - Call `bedrock-agentcore-control:CreateAgentRuntime` API
    - Store runtime ARN, ID, endpoint URL in DynamoDB
    - Store runtime ARN in SSM: `/${projectPrefix}/runtimes/{provider_id}/arn`
  - [x] 4.3 Implement error handling
    - Catch all exceptions during runtime operations
    - Update DynamoDB with FAILED status and error message
    - Log detailed errors to CloudWatch
  - [x] 4.4 Add retry logic (handled by Lambda DynamoDB Stream integration)
  - [x] 4.5 Create requirements.txt with dependencies (boto3, etc.)

- [x] 5. Add Runtime Provisioner Lambda to AppApiStack
  - [x] 5.1 Update AppApiStack CDK file (`infrastructure/lib/app-api-stack.ts`)
  - [x] 5.2 Define Lambda function resource
    - Runtime: Python 3.13
    - Memory: 512 MB
    - Timeout: 5 minutes
    - Code from `backend/lambda-functions/runtime-provisioner/`
    - Environment variables (project prefix, region, auth providers table name)
  - [x] 5.3 Create IAM role for Lambda
    - DynamoDB Stream read permissions
    - DynamoDB UpdateItem permissions (Auth Providers table)
    - Bedrock AgentCore permissions (CreateAgentRuntime, UpdateAgentRuntime, DeleteAgentRuntime, GetAgentRuntime)
    - SSM Parameter Store read/write permissions
    - ECR read permissions (DescribeRepositories, DescribeImages)
    - IAM PassRole permission (for runtime execution role)
    - CloudWatch Logs permissions
  - [x] 5.4 Add DynamoDB Stream event source
    - Use stream ARN from Auth Providers table
    - Set batch size: 1
    - Set starting position: LATEST
    - Enable retry with 3 attempts
  - [x] 5.5 Add CloudWatch log group with retention policy
  - [x] 5.6 Deploy AppApiStack with Runtime Provisioner Lambda

### Phase 4: Runtime Updater Lambda

- [x] 6. Create Runtime Updater Lambda Function
  - [x] 6.1 Create Lambda function code (`backend/lambda-functions/runtime-updater/`)
    - Implement EventBridge event handler
    - Query DynamoDB for all providers with existing runtimes
    - Fetch new container image URI from ECR
    - Update runtimes in parallel (max 5 concurrent)
    - Implement retry logic (3 attempts with exponential backoff)
    - Update DynamoDB status for each provider
    - Send SNS notification summary
  - [x] 6.2 Implement update logic
    - Fetch current runtime configuration via GetAgentRuntime
    - Call UpdateAgentRuntime with new container image
    - Preserve all other configuration (JWT auth, network, environment)
  - [x] 6.3 Create requirements.txt with dependencies

- [x] 7. Add Runtime Updater to AppApiStack
  - [x] 7.1 Define Lambda function resource in AppApiStack
    - Runtime: Python 3.13
    - Memory: 512 MB
    - Timeout: 15 minutes (for parallel updates)
    - Code from `backend/lambda-functions/runtime-updater/`
  - [x] 7.2 Create IAM role for Lambda
    - Bedrock AgentCore permissions (GetAgentRuntime, UpdateAgentRuntime)
    - DynamoDB Scan and UpdateItem permissions
    - SSM Parameter Store read permissions
    - ECR read permissions
    - SNS Publish permissions
  - [x] 7.3 Create SNS topic for alerts
    - Topic name: `{projectPrefix}-runtime-update-alerts`
    - Add email subscription (optional)
  - [x] 7.4 Create EventBridge rule
    - Detect SSM parameter changes: `/${projectPrefix}/inference-api/image-tag`
    - Target: Runtime Updater Lambda
  - [x] 7.5 Deploy updated AppApiStack with Runtime Updater

### Phase 5: Remove Entra ID Hardcoded Configuration

- [x] 8. Update Configuration Files
  - [x] 8.1 Update `infrastructure/lib/config.ts`
    - Remove `entraClientId` and `entraTenantId` from `AppConfig` interface
    - Remove `entraRedirectUri` from `AppApiConfig` interface
    - Remove Entra fields from `loadConfig()` function
  - [x] 8.2 Update `infrastructure/lib/app-api-stack.ts`
    - Remove `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_REDIRECT_URI` environment variables
    - Remove `ENTRA_CLIENT_SECRET` from secrets block
    - Remove authentication secret import (`authSecretArn`, `authSecret`)
    - Remove authentication secret permissions from task role
  - [x] 8.3 Update GitHub workflow files
    - Remove `CDK_ENTRA_CLIENT_ID`, `CDK_ENTRA_TENANT_ID`, `CDK_APP_API_ENTRA_REDIRECT_URI` from env sections
    - Remove `CDK_ENTRA_CLIENT_SECRET` from secrets
    - Files: `.github/workflows/infrastructure.yml`, `app-api.yml`, `inference-api.yml`
  - [x] 8.4 Update `cdk.context.json`
    - Remove Entra ID configuration (if present)
  - [x] 8.5 Update `scripts/common/load-env.sh`
    - Remove Entra ID environment variable exports
    - Remove Entra ID from context parameters function
    - Remove Entra ID from config display
  - [x] 8.6 Update stack deployment scripts
    - Remove Entra context parameters from `scripts/stack-infrastructure/synth.sh` and `deploy.sh`
    - Remove Entra context parameters from `scripts/stack-app-api/synth.sh` and `deploy.sh`
    - Remove Entra context parameters from `scripts/stack-inference-api/synth.sh` and `deploy.sh`

- [ ] 9. Update GitHub Repository Settings
  - [ ] 9.1 Delete GitHub Variables
    - Delete `CDK_ENTRA_CLIENT_ID`
    - Delete `CDK_ENTRA_TENANT_ID`
    - Delete `CDK_APP_API_ENTRA_REDIRECT_URI`
  - [ ] 9.2 Delete GitHub Secrets
    - Delete `CDK_ENTRA_CLIENT_SECRET`

- [x] 10. Update Backend Code
  - [x] 10.1 Search for Entra references in test files
    - Run: `grep -r "ENTRA_CLIENT_ID\|ENTRA_TENANT_ID\|ENTRA_REDIRECT_URI\|ENTRA_CLIENT_SECRET" backend/tests/`
  - [x] 10.2 Update test files to use mock auth providers from database
  - [x] 10.3 Remove Entra-specific test fixtures

- [ ] 11. Deploy Configuration Changes
  - [ ] 11.1 Deploy updated AppApiStack (without Entra environment variables)
  - [ ] 11.2 Verify deployment succeeds
  - [ ] 11.3 Verify no references to Entra configuration in deployed resources

### Phase 6: Frontend Updates

- [x] 12. Update Frontend API Service
  - [x] 12.1 Add method to fetch runtime endpoint URL
    - `getRuntimeEndpoint(providerId: string): Promise<string>`
    - Calls `GET /auth/runtime-endpoint`
  - [x] 12.2 Update auth service to track current provider ID
    - Extract provider ID from JWT token or user record
    - Store in signal: `currentProviderId = signal<string | null>(null)`

- [x] 13. Update Frontend Chat Service
  - [x] 13.1 Fetch runtime endpoint URL before making inference requests
    - Get provider ID from auth service
    - Fetch runtime endpoint URL from API service
    - Use runtime endpoint URL for all inference API calls
  - [x] 13.2 Handle runtime endpoint resolution errors
    - Display error message if provider not found
    - Display error message if runtime not ready

- [x] 14. Add Admin UI for Runtime Status
  - [x] 14.1 Create runtime status component
    - Display list of all providers with runtime status
    - Show runtime ARN, ID, endpoint URL
    - Show runtime status (PENDING, CREATING, READY, UPDATING, FAILED)
    - Show error details for failed runtimes
  - [x] 14.2 Add runtime version tracking
    - Display current deployed image tag
    - Display image tag per runtime
    - Show version mismatch indicators
  - [x] 14.3 Add manual update trigger button (optional)

### Phase 7: App API Backend Updates

- [x] 15. Add Runtime Endpoint API
  - [x] 15.1 Create new endpoint: `GET /auth/runtime-endpoint`
    - Extract provider ID from current user's JWT claims or user record
    - Fetch provider from DynamoDB
    - Return runtime endpoint URL
    - Return 404 if provider not found or runtime not ready
  - [x] 15.2 Add authentication middleware (require valid JWT)
  - [x] 15.3 Add error handling for missing runtime

### Phase 8: Monitoring and Observability

- [ ] 16. Add CloudWatch Metrics
  - [ ] 16.1 Create custom metrics in Runtime Updater Lambda
    - `UpdateSuccess`: Count of successful runtime updates
    - `UpdateFailure`: Count of failed runtime updates
    - `UpdateDuration`: Time taken to update all runtimes
    - `RuntimeCount`: Total number of active runtimes
  - [ ] 16.2 Namespace: `AgentCore/RuntimeUpdates`

- [ ] 17. Create CloudWatch Dashboard
  - [ ] 17.1 Add runtime update success rate graph
  - [ ] 17.2 Add runtime update duration graph
  - [ ] 17.3 Add runtime count by status
  - [ ] 17.4 Add failed update details

- [ ] 18. Configure CloudWatch Alarms
  - [ ] 18.1 Create alarm for runtime update failures
    - Trigger when `UpdateFailure > 0`
    - Send SNS notification
  - [ ] 18.2 Create alarm for high update duration
    - Trigger when `UpdateDuration > 30 minutes`
    - Send SNS notification
  - [ ] 18.3 Create alarm for runtime creation failures
    - Trigger on Lambda errors in Runtime Provisioner
    - Send SNS notification

### Phase 9: Testing and Validation

- [ ] 19. Test Runtime Provisioning
  - [ ] 19.1 Create test auth provider via admin UI
    - Verify DynamoDB Stream triggers Lambda
    - Verify runtime is created in AWS
    - Verify runtime ARN stored in DynamoDB
    - Verify runtime status changes: PENDING → CREATING → READY
  - [ ] 19.2 Test runtime provisioning failure scenarios
    - Invalid JWT configuration (bad discovery URL)
    - Invalid client ID
    - Network connectivity issues
    - Verify error message stored in DynamoDB
    - Verify SNS alert sent

- [ ] 20. Test Runtime Updates
  - [ ] 20.1 Push new Docker image to ECR
    - Verify SSM parameter updated
    - Verify EventBridge triggers Lambda
    - Verify all runtimes updated in parallel
    - Verify DynamoDB status updated
  - [ ] 20.2 Test runtime update failure scenarios
    - Runtime not found (deleted externally)
    - Network connectivity issues
    - Verify retry logic (3 attempts)
    - Verify SNS alert sent

- [ ] 21. Test End-to-End Authentication Flow
  - [ ] 21.1 Authenticate with test provider
    - Verify JWT token received
    - Verify provider ID extracted from token
  - [ ] 21.2 Fetch runtime endpoint URL
    - Verify correct endpoint URL returned
    - Verify 404 if provider not found
  - [ ] 21.3 Call runtime endpoint directly
    - Verify JWT validated by runtime
    - Verify request processed successfully
  - [ ] 21.4 Test with multiple providers
    - Create 2-3 test providers
    - Verify each has its own runtime
    - Verify users can authenticate with any provider

- [ ] 22. Test Provider Deletion
  - [ ] 22.1 Delete test provider via admin UI
    - Verify DynamoDB Stream triggers Lambda
    - Verify runtime deleted in AWS
    - Verify SSM parameters cleaned up
    - Verify DynamoDB record deleted

- [ ] 23. Validate Configuration Removal
  - [ ] 23.1 Search codebase for Entra references
    - Run: `grep -r "ENTRA_CLIENT_ID\|ENTRA_TENANT_ID\|ENTRA_REDIRECT_URI\|ENTRA_CLIENT_SECRET" .`
    - Verify no matches found (except in documentation)
  - [ ] 23.2 Verify GitHub Variables and Secrets deleted
  - [ ] 23.3 Verify all auth providers managed via database
  - [ ] 23.4 Test end-to-end authentication flow (no Entra hardcoded config)

### Phase 10: Documentation and Cleanup

- [ ] 24. Update Documentation
  - [ ] 24.1 Update README with new provider management process
  - [ ] 24.2 Create operational runbook for runtime management
  - [ ] 24.3 Create troubleshooting guide for common issues
  - [ ] 24.4 Document monitoring and alerting setup

- [ ] 25. Cleanup and Optimization
  - [ ] 25.1 Remove unused SSM parameters (old Entra configuration)
  - [ ] 25.2 Remove unused Secrets Manager secrets (old Entra client secret)
  - [ ] 25.3 Verify no orphaned resources in AWS
  - [ ] 25.4 Optimize Lambda memory and timeout settings based on actual usage

## Success Criteria

- [ ] Runtime provisioning success rate > 95%
- [ ] Runtime update success rate > 98%
- [ ] Average provisioning time < 5 minutes
- [ ] Average update time < 5 minutes per runtime
- [ ] Zero authentication failures due to routing issues
- [ ] Admin UI shows real-time runtime status
- [ ] SNS alerts sent for all failures
- [ ] CloudWatch dashboard operational
- [ ] All runtimes share Memory, Gateway, Code Interpreter, Browser
- [ ] Users from any provider can access AI agent
- [ ] No references to hardcoded Entra ID configuration in codebase

## Notes

- Tasks should be executed in order (phases are sequential)
- Each phase should be tested before moving to the next
- Maintain a rollback plan for each deployment
- Schedule deployments during low-usage periods
- Communicate expected downtime to users (5-10 minutes during Phase 2)
- **Architectural Decision**: Lambda functions are integrated into the App API stack rather than a separate RuntimeProvisionerStack to avoid unnecessary cross-stack dependencies. The App API stack already depends on the Inference API stack for shared resource ARNs, making it the natural location for runtime management logic.

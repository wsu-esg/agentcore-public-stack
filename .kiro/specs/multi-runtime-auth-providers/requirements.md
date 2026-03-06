# Multi-Runtime Authentication Providers - Requirements

## Feature Overview

Implement dynamic multi-runtime deployment strategy to support multiple OIDC authentication providers. When an admin adds a new authentication provider via the UI, automatically provision a dedicated AWS Bedrock AgentCore Runtime with that provider's JWT authorizer configuration.

## Problem Statement

The application currently supports dynamic database-driven OIDC provider management through the admin UI. However, the AgentCore Runtime is deployed with a single, hardcoded JWT authorizer pointing to Microsoft Entra ID. This creates a mismatch:

- ✅ App API (port 8000) can authenticate users from any provider in the database
- ❌ Inference API (AgentCore Runtime, port 8001) only accepts Entra ID tokens
- ❌ Users authenticated via new providers cannot invoke the AI agent

## User Stories

### 1. Admin Provider Management
**As a** system administrator  
**I want to** add new OIDC authentication providers through the admin UI  
**So that** users from different identity providers can access the platform

**Acceptance Criteria:**
- 1.1 When I create a new auth provider, a dedicated AgentCore Runtime is automatically provisioned
- 1.2 The runtime is configured with the provider's JWT authorizer (issuer URL, client ID, JWKS URI)
- 1.3 Runtime creation status is visible in the admin UI (PENDING → CREATING → READY → FAILED)
- 1.4 Runtime provisioning completes within 5 minutes
- 1.5 If provisioning fails, error details are displayed in the admin UI

### 2. Automatic Runtime Updates
**As a** system administrator  
**I want to** update authentication provider configuration  
**So that** changes are reflected in the runtime without manual intervention

**Acceptance Criteria:**
- 2.1 When I update a provider's issuer URL or client ID, the runtime is automatically updated
- 2.2 Runtime update status is visible (UPDATING)
- 2.3 Active sessions are not interrupted during updates
- 2.4 Update failures are logged and alerted

### 3. Container Image Synchronization
**As a** DevOps engineer  
**I want to** deploy new container images  
**So that** all provider runtimes are automatically updated to the latest code

**Acceptance Criteria:**
- 3.1 When a new Docker image is pushed to ECR, all provider runtimes are updated automatically
- 3.2 Updates happen in parallel to minimize total update time
- 3.3 Failed updates are retried with exponential backoff
- 3.4 SNS notifications are sent for update failures
- 3.5 Admin dashboard shows which runtimes are on which image versions

### 4. Provider Deletion
**As a** system administrator  
**I want to** delete authentication providers  
**So that** unused providers and their resources are cleaned up

**Acceptance Criteria:**
- 4.1 When I delete a provider, its runtime is automatically deleted
- 4.2 SSM parameters for the provider are cleaned up
- 4.3 Deletion is confirmed before proceeding
- 4.4 Active sessions using the provider are gracefully terminated

### 5. User Authentication Routing
**As a** user  
**I want to** authenticate with my organization's identity provider  
**So that** I can access the AI agent with my existing credentials

**Acceptance Criteria:**
- 5.1 Frontend determines my provider ID from my JWT token or auth service
- 5.2 Frontend fetches the correct runtime endpoint URL for my provider from App API
- 5.3 Frontend calls my provider's runtime endpoint directly
- 5.4 Runtime validates my JWT token using my provider's JWKS
- 5.5 Authentication failures provide clear error messages

### 6. Shared Resource Access
**As a** user authenticated via any provider  
**I want to** access shared platform resources  
**So that** my experience is consistent regardless of provider

**Acceptance Criteria:**
- 6.1 All runtimes share the same AgentCore Memory instance
- 6.2 All runtimes share the same AgentCore Gateway instance
- 6.3 All runtimes share the same Code Interpreter and Browser instances
- 6.4 All runtimes access the same DynamoDB tables (users, roles, tools, etc.)
- 6.5 All runtimes access the same S3 buckets (uploads, vectors)

## Technical Requirements

### Architecture Constraints

1. **Stack Separation**: App API and Inference API are in separate CDK stacks
2. **Shared Resources**: Memory, Gateway, Code Interpreter, Browser are shared across all runtimes
3. **AWS Quotas**: Support up to 1,000 runtimes per account (AWS limit)
4. **Runtime Creation Time**: 2-5 minutes per runtime
5. **Deployment Order**: Infrastructure → Gateway → App API → Inference API

### Database Schema

Auth Providers table must track runtime information:

```
PK: AUTH_PROVIDER#{provider_id}
SK: AUTH_PROVIDER#{provider_id}
Attributes:
  - agentcoreRuntimeArn: string (optional)
  - agentcoreRuntimeId: string (optional)
  - agentcoreRuntimeEndpointUrl: string (optional)
  - agentcoreRuntimeStatus: string (PENDING | CREATING | READY | UPDATING | FAILED | UPDATE_FAILED)
  - agentcoreRuntimeError: string (optional)
```

### Event-Driven Architecture

1. **DynamoDB Streams**: Enabled on Auth Providers table
2. **Lambda Trigger**: Runtime Provisioner Lambda triggered by stream events
3. **EventBridge**: Triggers Runtime Updater Lambda when image tag changes in SSM
4. **SNS Notifications**: Alerts for provisioning/update failures

### Routing Strategy

**Direct Runtime Invocation**:
- Frontend fetches runtime endpoint URL from App API based on user's provider ID
- Frontend calls provider-specific runtime endpoint directly
- No ALB routing needed (AgentCore Runtimes are AWS-managed services with their own HTTPS endpoints)

**Endpoint Format**: `https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{runtime-arn}/invocations`

### Security

1. **IAM Roles**: Shared execution role for all runtimes (or per-runtime if needed)
2. **JWT Validation**: Each runtime validates tokens from its specific provider
3. **Resource Access**: All runtimes have identical permissions to shared resources
4. **Secrets**: Client secrets stored in Secrets Manager, referenced by provider ID

## Non-Functional Requirements

### Performance
- Runtime provisioning: < 5 minutes
- Runtime updates: < 5 minutes per runtime
- Image updates: All runtimes updated within 30 minutes (parallel execution)
- Request latency: No added latency vs single runtime (direct runtime invocation)

### Scalability
- Support 1-10 providers initially
- Architecture supports up to 1,000 providers (AWS quota)
- Parallel runtime updates (max 5 concurrent)

### Reliability
- Retry logic for transient failures (3 attempts with exponential backoff)
- SNS alerts for persistent failures
- CloudWatch metrics for monitoring
- Failed updates don't affect other runtimes

### Observability
- CloudWatch dashboard for runtime status
- Admin UI shows runtime version and status
- Logs for all provisioning/update operations
- Metrics: update success rate, update duration, runtime count

### Cost
- Estimated $20/month additional cost for 5 providers (vs single runtime)
- No base cost per runtime (serverless, pay per invocation)
- Shared resources minimize overhead

## Dependencies

### Existing Infrastructure
- App API Stack (DynamoDB tables, auth provider management)
- Inference API Stack (shared AgentCore resources)
- Infrastructure Stack (VPC, ALB, ECS Cluster)

### New Infrastructure
- Runtime Provisioner Lambda + Stack
- Runtime Updater Lambda
- DynamoDB Streams on Auth Providers table
- EventBridge rule for image tag changes
- SNS topic for alerts
- App API endpoint for runtime URL lookup

### Code Changes
- Auth Provider models (add runtime tracking fields)
- App API endpoint (GET /auth/runtime-endpoint)
- Frontend API service (fetch runtime endpoint URL per provider)
- Admin UI (display runtime status)

## Out of Scope

- Multi-region runtime deployment
- Blue-green deployment for runtimes
- Custom routing logic beyond header/path-based
- Runtime auto-scaling (handled by AgentCore)
- Provider-specific resource quotas (use existing quota system)

## Success Metrics

1. **Provisioning Success Rate**: > 95% of runtime creations succeed
2. **Update Success Rate**: > 98% of runtime updates succeed
3. **Provisioning Time**: < 5 minutes average
4. **Update Time**: < 5 minutes per runtime average
5. **User Impact**: Zero authentication failures due to routing issues
6. **Operational Overhead**: < 1 hour/week for runtime management

## Risks and Mitigations

### Risk 1: Runtime Creation Failures
**Impact**: Users cannot authenticate with new provider  
**Mitigation**: Retry logic, detailed error logging, SNS alerts, admin UI shows status

### Risk 2: Runtime Endpoint Resolution Failures
**Impact**: Requests cannot be routed to correct runtime  
**Mitigation**: Comprehensive testing, endpoint validation, fallback error handling

### Risk 3: Image Update Failures
**Impact**: Runtimes running stale code  
**Mitigation**: Parallel updates with retry, SNS alerts, admin dashboard shows versions

### Risk 4: Cost Overruns
**Impact**: Unexpected AWS charges  
**Mitigation**: CloudWatch cost monitoring, runtime count limits, cost alerts

### Risk 5: Shared Resource Contention
**Impact**: Performance degradation  
**Mitigation**: Monitor resource usage, implement quotas, scale shared resources

## Future Enhancements

1. **Blue-Green Deployment**: Zero-downtime runtime updates
2. **Provider-Specific Resources**: Dedicated Memory/Gateway per provider
3. **Multi-Region Support**: Runtimes in multiple AWS regions
4. **Auto-Scaling**: Dynamic runtime provisioning based on load
5. **Cost Allocation**: Per-provider cost tracking and billing

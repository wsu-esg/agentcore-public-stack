# Design Document: Shared Tables Refactor

## Overview

This design addresses a circular SSM parameter dependency between CDK stacks that prevents deployment to fresh AWS accounts. Currently, `AppApiStack` creates 7 shared DynamoDB tables and a Secrets Manager resource that are consumed by both `AppApiStack` and `InferenceApiStack`. Because `AppApiStack` also imports SSM parameters from `InferenceApiStack` and `RagIngestionStack`, a circular dependency exists.

The solution moves the shared tables and Secrets Manager resource from `AppApiStack` to `InfrastructureStack` (the foundation layer), establishing a clean linear deployment order: InfrastructureStack → RagIngestionStack → InferenceApiStack → AppApiStack.

This is a pure infrastructure refactoring with zero impact on application code, Lambda functions, deployment scripts, or frontend code. The refactor preserves all table schemas, GSI definitions, IAM permissions, and environment variables exactly as they exist today.

## Architecture

### Current Architecture (Circular Dependency)

```
InfrastructureStack
  ├─ Creates: VPC, ALB, ECS Cluster
  ├─ Creates: Users, AppRoles, OidcState, ApiKeys, OAuth tables
  └─ Exports: Network resources, core table ARNs

RagIngestionStack
  ├─ Imports: Network resources from InfrastructureStack
  ├─ Creates: Assistants table, Documents bucket, Vector bucket
  └─ Exports: RAG resource ARNs

InferenceApiStack
  ├─ Imports: Network resources from InfrastructureStack
  ├─ Imports: RAG resources from RagIngestionStack
  ├─ Imports: Shared tables from AppApiStack ❌ CIRCULAR
  ├─ Creates: AgentCore Memory, Runtime execution role
  └─ Exports: Memory ARN, Runtime role ARN

AppApiStack
  ├─ Imports: Network resources from InfrastructureStack
  ├─ Imports: RAG resources from RagIngestionStack
  ├─ Imports: Memory ARN from InferenceApiStack ❌ CIRCULAR
  ├─ Creates: Shared tables (UserQuotas, QuotaEvents, etc.) ❌ WRONG LAYER
  ├─ Creates: auth-provider-secrets ❌ WRONG LAYER
  ├─ Creates: App-specific resources (Assistants, UserFiles)
  └─ Exports: Shared table ARNs

Circular dependency: AppApiStack → InferenceApiStack → AppApiStack
```

### Target Architecture (Linear Dependency)

```
InfrastructureStack (Foundation Layer)
  ├─ Creates: VPC, ALB, ECS Cluster
  ├─ Creates: Core tables (Users, AppRoles, OidcState, ApiKeys, OAuth)
  ├─ Creates: Shared tables (UserQuotas, QuotaEvents, SessionsMetadata, etc.) ✅
  ├─ Creates: auth-provider-secrets ✅
  └─ Exports: Network resources, all table ARNs

RagIngestionStack
  ├─ Imports: Network resources from InfrastructureStack
  ├─ Creates: Assistants table, Documents bucket, Vector bucket
  └─ Exports: RAG resource ARNs

InferenceApiStack
  ├─ Imports: Network resources from InfrastructureStack
  ├─ Imports: Shared tables from InfrastructureStack ✅
  ├─ Imports: RAG resources from RagIngestionStack
  ├─ Creates: AgentCore Memory, Runtime execution role
  └─ Exports: Memory ARN, Runtime role ARN

AppApiStack (Service Layer)
  ├─ Imports: Network resources from InfrastructureStack
  ├─ Imports: Shared tables from InfrastructureStack ✅
  ├─ Imports: RAG resources from RagIngestionStack
  ├─ Imports: Memory ARN from InferenceApiStack
  ├─ Creates: App-specific resources (Assistants, UserFiles)
  └─ Creates: ECS service, Lambda functions

Linear dependency: InfrastructureStack → RagIngestionStack → InferenceApiStack → AppApiStack ✅
```

### Stack Dependency Graph

The refactor transforms the dependency graph from cyclic to acyclic:

**Before (Cyclic):**
- InfrastructureStack: no dependencies
- RagIngestionStack: depends on InfrastructureStack
- InferenceApiStack: depends on InfrastructureStack, RagIngestionStack, AppApiStack
- AppApiStack: depends on InfrastructureStack, RagIngestionStack, InferenceApiStack

**After (Acyclic):**
- InfrastructureStack: no dependencies
- RagIngestionStack: depends on InfrastructureStack
- InferenceApiStack: depends on InfrastructureStack, RagIngestionStack
- AppApiStack: depends on InfrastructureStack, RagIngestionStack, InferenceApiStack

## Components and Interfaces

### 1. Shared DynamoDB Tables (Moving to InfrastructureStack)

#### 1.1 UserQuotas Table
- **Purpose**: Quota assignments for users and roles
- **Schema**: PK (String), SK (String)
- **Billing**: PAY_PER_REQUEST
- **Features**: Point-in-time recovery, AWS_MANAGED encryption
- **GSIs**:
  - AssignmentTypeIndex: GSI1PK, GSI1SK (ALL projection)
  - UserAssignmentIndex: GSI2PK, GSI2SK (ALL projection)
  - RoleAssignmentIndex: GSI3PK, GSI3SK (ALL projection)
  - UserOverrideIndex: GSI4PK, GSI4SK (ALL projection)
  - AppRoleAssignmentIndex: GSI6PK, GSI6SK (ALL projection)
- **SSM Exports**:
  - `/${projectPrefix}/quota/user-quotas-table-name`
  - `/${projectPrefix}/quota/user-quotas-table-arn`

#### 1.2 QuotaEvents Table
- **Purpose**: Quota usage event tracking
- **Schema**: PK (String), SK (String)
- **Billing**: PAY_PER_REQUEST
- **Features**: Point-in-time recovery, AWS_MANAGED encryption
- **GSIs**:
  - TierEventIndex: GSI5PK, GSI5SK (ALL projection)
- **SSM Exports**:
  - `/${projectPrefix}/quota/quota-events-table-name`
  - `/${projectPrefix}/quota/quota-events-table-arn`

#### 1.3 SessionsMetadata Table
- **Purpose**: Message-level metadata for cost tracking
- **Schema**: PK (String), SK (String)
- **Billing**: PAY_PER_REQUEST
- **Features**: Point-in-time recovery, AWS_MANAGED encryption, TTL attribute "ttl"
- **GSIs**:
  - UserTimestampIndex: GSI1PK, GSI1SK (ALL projection)
  - SessionLookupIndex: GSI_PK, GSI_SK (ALL projection)
- **SSM Exports**:
  - `/${projectPrefix}/cost-tracking/sessions-metadata-table-name`
  - `/${projectPrefix}/cost-tracking/sessions-metadata-table-arn`

#### 1.4 UserCostSummary Table
- **Purpose**: Pre-aggregated cost summaries for quota checks
- **Schema**: PK (String), SK (String)
- **Billing**: PAY_PER_REQUEST
- **Features**: Point-in-time recovery, AWS_MANAGED encryption
- **GSIs**:
  - PeriodCostIndex: GSI2PK, GSI2SK (INCLUDE projection: userId, totalCost, totalRequests, lastUpdated)
- **SSM Exports**:
  - `/${projectPrefix}/cost-tracking/user-cost-summary-table-name`
  - `/${projectPrefix}/cost-tracking/user-cost-summary-table-arn`

#### 1.5 SystemCostRollup Table
- **Purpose**: System-wide cost metrics for admin dashboard
- **Schema**: PK (String), SK (String)
- **Billing**: PAY_PER_REQUEST
- **Features**: Point-in-time recovery, AWS_MANAGED encryption
- **SSM Exports**:
  - `/${projectPrefix}/cost-tracking/system-cost-rollup-table-name`
  - `/${projectPrefix}/cost-tracking/system-cost-rollup-table-arn`

#### 1.6 ManagedModels Table
- **Purpose**: Model management and pricing data
- **Schema**: PK (String), SK (String)
- **Billing**: PAY_PER_REQUEST
- **Features**: Point-in-time recovery, AWS_MANAGED encryption
- **GSIs**:
  - ModelIdIndex: GSI1PK, GSI1SK (ALL projection)
- **SSM Exports**:
  - `/${projectPrefix}/admin/managed-models-table-name`
  - `/${projectPrefix}/admin/managed-models-table-arn`

#### 1.7 AuthProviders Table
- **Purpose**: OIDC authentication provider configuration
- **Schema**: PK (String), SK (String)
- **Billing**: PAY_PER_REQUEST
- **Features**: Point-in-time recovery, AWS_MANAGED encryption, DynamoDB Stream (NEW_AND_OLD_IMAGES)
- **GSIs**:
  - EnabledProvidersIndex: GSI1PK, GSI1SK (ALL projection)
- **SSM Exports**:
  - `/${projectPrefix}/auth/auth-providers-table-name`
  - `/${projectPrefix}/auth/auth-providers-table-arn`
  - `/${projectPrefix}/auth/auth-providers-stream-arn`

### 2. Secrets Manager Resource (Moving to InfrastructureStack)

#### 2.1 auth-provider-secrets
- **Purpose**: OIDC authentication provider client secrets
- **Type**: AWS Secrets Manager Secret
- **Content**: JSON object mapping provider IDs to client secrets
- **Removal Policy**: RETAIN (preserve secrets on stack deletion)
- **SSM Export**:
  - `/${projectPrefix}/auth/auth-provider-secrets-arn`

### 3. Resources Remaining in AppApiStack

The following resources are NOT moved because they are only used by AppApiStack:

#### 3.1 Assistants Table
- **Purpose**: Assistant configuration and metadata
- **Consumers**: AppApiStack only
- **GSIs**: OwnerStatusIndex, VisibilityStatusIndex, SharedWithIndex

#### 3.2 AssistantsDocumentsBucket
- **Purpose**: Document storage for RAG ingestion
- **Consumers**: AppApiStack only

#### 3.3 AssistantsVectorBucket and AssistantsVectorIndex
- **Purpose**: Vector embeddings for RAG
- **Consumers**: AppApiStack only

#### 3.4 UserFiles Table and UserFilesBucket
- **Purpose**: User file uploads and metadata
- **Consumers**: AppApiStack only

#### 3.5 RuntimeProvisioner Lambda
- **Purpose**: Provisions AgentCore runtimes on auth provider changes
- **Consumers**: AppApiStack only
- **Event Source**: AuthProviders table DynamoDB Stream

#### 3.6 RuntimeUpdater Lambda
- **Purpose**: Updates AgentCore runtimes on image tag changes
- **Consumers**: AppApiStack only

### 4. SSM Parameter Paths

All SSM parameter paths remain unchanged to maintain compatibility:

| Resource | Name Parameter | ARN Parameter | Stream ARN Parameter |
|----------|---------------|---------------|---------------------|
| UserQuotas | `/${projectPrefix}/quota/user-quotas-table-name` | `/${projectPrefix}/quota/user-quotas-table-arn` | - |
| QuotaEvents | `/${projectPrefix}/quota/quota-events-table-name` | `/${projectPrefix}/quota/quota-events-table-arn` | - |
| SessionsMetadata | `/${projectPrefix}/cost-tracking/sessions-metadata-table-name` | `/${projectPrefix}/cost-tracking/sessions-metadata-table-arn` | - |
| UserCostSummary | `/${projectPrefix}/cost-tracking/user-cost-summary-table-name` | `/${projectPrefix}/cost-tracking/user-cost-summary-table-arn` | - |
| SystemCostRollup | `/${projectPrefix}/cost-tracking/system-cost-rollup-table-name` | `/${projectPrefix}/cost-tracking/system-cost-rollup-table-arn` | - |
| ManagedModels | `/${projectPrefix}/admin/managed-models-table-name` | `/${projectPrefix}/admin/managed-models-table-arn` | - |
| AuthProviders | `/${projectPrefix}/auth/auth-providers-table-name` | `/${projectPrefix}/auth/auth-providers-table-arn` | `/${projectPrefix}/auth/auth-providers-stream-arn` |
| auth-provider-secrets | - | `/${projectPrefix}/auth/auth-provider-secrets-arn` | - |

### 5. IAM Permission Patterns

#### 5.1 AppApiStack ECS Task Role
The ECS task role must maintain the same DynamoDB permissions after the refactor. Instead of using `table.grantReadWriteData()` on local table constructs, it will use explicit IAM policy statements with imported ARNs:

**Before (local table):**
```typescript
userQuotasTable.grantReadWriteData(taskDefinition.taskRole);
```

**After (imported ARN):**
```typescript
const userQuotasTableArn = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/quota/user-quotas-table-arn`
);

taskDefinition.taskRole.addToPrincipalPolicy(
  new iam.PolicyStatement({
    sid: 'UserQuotasTableAccess',
    effect: iam.Effect.ALLOW,
    actions: [
      'dynamodb:GetItem',
      'dynamodb:PutItem',
      'dynamodb:UpdateItem',
      'dynamodb:DeleteItem',
      'dynamodb:Query',
      'dynamodb:Scan',
      'dynamodb:BatchGetItem',
      'dynamodb:BatchWriteItem',
    ],
    resources: [
      userQuotasTableArn,
      `${userQuotasTableArn}/index/*`,
    ],
  })
);
```

#### 5.2 RuntimeProvisioner Lambda
The RuntimeProvisioner Lambda requires special handling because it uses the AuthProviders table as a DynamoDB Stream event source. The table must be reconstructed using `dynamodb.Table.fromTableAttributes()`:

```typescript
const authProvidersTableName = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/auth/auth-providers-table-name`
);
const authProvidersTableArn = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/auth/auth-providers-table-arn`
);
const authProvidersStreamArn = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/auth/auth-providers-stream-arn`
);

const authProvidersTable = dynamodb.Table.fromTableAttributes(this, 'ImportedAuthProvidersTable', {
  tableName: authProvidersTableName,
  tableArn: authProvidersTableArn,
  tableStreamArn: authProvidersStreamArn,
});

// Now can use table.grantStreamRead() and add event source
authProvidersTable.grantStreamRead(runtimeProvisionerFunction);
runtimeProvisionerFunction.addEventSource(
  new lambdaEventSources.DynamoEventSource(authProvidersTable, {
    startingPosition: lambda.StartingPosition.LATEST,
    batchSize: 1,
    retryAttempts: 3,
    bisectBatchOnError: true,
  })
);
```

#### 5.3 InferenceApiStack Runtime Execution Role
The InferenceApiStack already imports shared table ARNs via SSM and grants permissions using explicit IAM policy statements. No changes are required to InferenceApiStack beyond updating the comments to reflect that tables are now imported from InfrastructureStack instead of AppApiStack.

### 6. Environment Variables

The AppApiStack ECS container environment variables must continue to reference the same table names. The only change is that table names are now imported from SSM instead of being local references:

**Before (local table):**
```typescript
environment: {
  DYNAMODB_QUOTA_TABLE: userQuotasTable.tableName,
  DYNAMODB_EVENTS_TABLE: quotaEventsTable.tableName,
  // ...
}
```

**After (imported from SSM):**
```typescript
const userQuotasTableName = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/quota/user-quotas-table-name`
);
const quotaEventsTableName = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/quota/quota-events-table-name`
);

environment: {
  DYNAMODB_QUOTA_TABLE: userQuotasTableName,
  DYNAMODB_EVENTS_TABLE: quotaEventsTableName,
  // ...
}
```

## Data Models

No data model changes are required. All table schemas, partition keys, sort keys, GSI definitions, and attribute types remain identical. The refactor only changes which CDK stack creates the tables, not the table definitions themselves.

### Table Schema Preservation

Each table definition must be copied exactly from AppApiStack to InfrastructureStack with the following preserved:
- Table name generation: `getResourceName(config, '<table-suffix>')`
- Partition key and sort key names and types
- Billing mode: `PAY_PER_REQUEST`
- Point-in-time recovery: `true`
- Encryption: `AWS_MANAGED`
- Removal policy: `getRemovalPolicy(config)`
- GSI names, key schemas, and projection types
- Special features: TTL attribute (SessionsMetadata), DynamoDB Stream (AuthProviders)

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Analysis

This refactoring is a pure infrastructure change that modifies CDK stack definitions without altering runtime application behavior. All acceptance criteria specify infrastructure configuration requirements (table schemas, SSM parameter paths, IAM policies, deployment order) rather than functional runtime properties.

The correctness of this refactor is validated through:
1. **CloudFormation Template Comparison**: Synthesized templates before/after should show tables moved from AppApiStack to InfrastructureStack with identical configurations
2. **Deployment Testing**: Deploying to a fresh AWS account should succeed without circular dependency errors
3. **Integration Testing**: Application code should function identically after the refactor
4. **Manual Verification**: SSM parameters, IAM policies, and environment variables should match pre-refactor values

### Property-Based Testing Applicability

After analyzing all 8 requirements and their 40+ acceptance criteria, **none are suitable for property-based testing** because:
- They specify infrastructure configuration, not runtime behavior
- They describe CDK code structure, not application logic
- They define deployment sequencing, not functional properties
- They are one-time deployment concerns, not repeatable runtime properties

Property-based testing is designed for validating universal properties across many generated inputs (e.g., "for all valid tasks, adding then removing should restore the original state"). Infrastructure refactoring does not have this characteristic—it's a one-time structural change validated through deployment testing and template comparison.

### No Testable Properties

Based on the prework analysis, there are no acceptance criteria that can be expressed as universally quantified properties suitable for property-based testing. All requirements are infrastructure configuration specifications that should be validated through:
- CDK synthesis and CloudFormation template inspection
- Deployment to test/staging environments
- Integration tests verifying application behavior is unchanged
- Manual verification of SSM parameters and IAM policies

## Error Handling

### Deployment Errors

#### Circular Dependency Detection
**Error**: `ValidationError: Unable to fetch parameters [/${projectPrefix}/...] (Parameter does not exist)`

**Cause**: Attempting to deploy AppApiStack before InfrastructureStack has created and exported the shared table SSM parameters.

**Resolution**: Deploy stacks in the correct order:
1. InfrastructureStack
2. RagIngestionStack
3. InferenceApiStack
4. AppApiStack

#### Missing SSM Parameters
**Error**: `Parameter /${projectPrefix}/quota/user-quotas-table-arn does not exist`

**Cause**: InfrastructureStack was deployed without the shared table definitions, or SSM parameter exports are missing.

**Resolution**: Verify InfrastructureStack includes all 7 shared table definitions and their SSM parameter exports.

#### IAM Permission Errors
**Error**: `User: arn:aws:sts::123456789012:assumed-role/... is not authorized to perform: dynamodb:GetItem on resource: arn:aws:dynamodb:...`

**Cause**: IAM policy statements in AppApiStack or InferenceApiStack are missing required permissions after switching from `table.grantReadWriteData()` to explicit policy statements.

**Resolution**: Verify all IAM policy statements include the same actions as the original `grantReadWriteData()` calls:
- GetItem, PutItem, UpdateItem, DeleteItem
- Query, Scan
- BatchGetItem, BatchWriteItem (where applicable)
- Permissions for both table ARN and `${tableArn}/index/*`

#### DynamoDB Stream Event Source Errors
**Error**: `Cannot add event source: table stream ARN is undefined`

**Cause**: RuntimeProvisioner Lambda cannot attach to AuthProviders table stream because the table was not reconstructed using `fromTableAttributes()` with `tableStreamArn`.

**Resolution**: Use `dynamodb.Table.fromTableAttributes()` to reconstruct the table reference with all three attributes: `tableName`, `tableArn`, and `tableStreamArn`.

### Rollback Strategy

If deployment fails or issues are discovered after deployment:

1. **Immediate Rollback**: Revert the CDK code changes and redeploy the original stack configuration
2. **Data Preservation**: All tables use `getRemovalPolicy(config)` which is RETAIN for production, ensuring no data loss during rollback
3. **SSM Parameter Cleanup**: Manually delete duplicate SSM parameters if both old and new stacks created them
4. **Gradual Migration**: Deploy to dev/staging environments first to validate the refactor before production

## Testing Strategy

### Unit Testing

This refactor does not require new unit tests because:
- No application code changes (backend, frontend, Lambda functions)
- No new business logic or algorithms
- Infrastructure changes are validated through deployment testing

### Integration Testing

Integration tests should verify that application behavior is unchanged after the refactor:

1. **Quota Management Tests**
   - Create quota assignments
   - Query quota usage
   - Verify quota enforcement

2. **Cost Tracking Tests**
   - Record session metadata
   - Query user cost summaries
   - Verify cost aggregation

3. **Auth Provider Tests**
   - Create/update auth providers
   - Verify RuntimeProvisioner Lambda triggers on changes
   - Verify runtime provisioning succeeds

4. **Model Management Tests**
   - Create/update managed models
   - Query model pricing data

### Deployment Testing

The primary validation for this refactor is successful deployment to a fresh AWS account:

1. **Fresh Account Deployment**
   - Deploy to a new AWS account with no existing resources
   - Verify deployment order: InfrastructureStack → RagIngestionStack → InferenceApiStack → AppApiStack
   - Verify no circular dependency errors
   - Verify all SSM parameters are created correctly

2. **Update Deployment**
   - Deploy the refactored stacks to an existing environment
   - Verify CloudFormation detects table moves (delete from AppApiStack, create in InfrastructureStack)
   - Verify no data loss (tables use RETAIN removal policy)
   - Verify application continues functioning

3. **SSM Parameter Verification**
   - Query all SSM parameters after deployment
   - Verify parameter paths match expected values
   - Verify parameter values (table names, ARNs) are correct

4. **IAM Permission Verification**
   - Inspect ECS task role policies
   - Inspect Lambda function role policies
   - Verify all required DynamoDB actions are granted
   - Verify index ARNs are included in resource lists

### CloudFormation Template Comparison

Before deploying, compare synthesized CloudFormation templates:

```bash
# Synthesize before refactor
git checkout main
cd infrastructure
npx cdk synth InfrastructureStack > /tmp/infra-before.yaml
npx cdk synth AppApiStack > /tmp/app-before.yaml

# Synthesize after refactor
git checkout feature/shared-tables-refactor
npx cdk synth InfrastructureStack > /tmp/infra-after.yaml
npx cdk synth AppApiStack > /tmp/app-after.yaml

# Compare
diff /tmp/infra-before.yaml /tmp/infra-after.yaml  # Should show 7 new tables
diff /tmp/app-before.yaml /tmp/app-after.yaml      # Should show 7 tables removed
```

Expected changes:
- InfrastructureStack: +7 DynamoDB tables, +1 Secrets Manager secret, +9 SSM parameters
- AppApiStack: -7 DynamoDB tables, -1 Secrets Manager secret, -9 SSM parameters, +SSM imports, +explicit IAM policies

### Manual Verification Checklist

After deployment, manually verify:

- [ ] All 7 shared tables exist in DynamoDB console
- [ ] All tables have correct schemas (PK, SK, GSIs)
- [ ] All tables have correct billing mode (PAY_PER_REQUEST)
- [ ] All tables have point-in-time recovery enabled
- [ ] SessionsMetadata table has TTL attribute configured
- [ ] AuthProviders table has DynamoDB Stream enabled
- [ ] auth-provider-secrets exists in Secrets Manager
- [ ] All SSM parameters exist with correct paths
- [ ] AppApiStack ECS task role has DynamoDB permissions
- [ ] InferenceApiStack runtime role has DynamoDB permissions
- [ ] RuntimeProvisioner Lambda has DynamoDB Stream event source
- [ ] Application endpoints respond correctly
- [ ] No errors in CloudWatch Logs

## Implementation Notes

### Code Organization

The refactor touches only CDK stack files:
- `infrastructure/lib/infrastructure-stack.ts` (add table definitions)
- `infrastructure/lib/app-api-stack.ts` (remove table definitions, add SSM imports)
- `infrastructure/lib/inference-api-stack.ts` (update comments only)

### Table Definition Copy-Paste

When copying table definitions from AppApiStack to InfrastructureStack:
1. Copy the entire table definition block (including comments)
2. Copy the GSI definitions exactly
3. Copy the SSM parameter exports exactly
4. Verify `getResourceName(config, '<suffix>')` calls use the same suffix
5. Verify `getRemovalPolicy(config)` is used (not hardcoded)

### Import Pattern

When importing tables in AppApiStack:
1. Import table name via SSM
2. Import table ARN via SSM
3. Import stream ARN via SSM (AuthProviders only)
4. Use imported values in environment variables
5. Use imported ARNs in IAM policy statements
6. Use `fromTableAttributes()` for tables with event sources

### Deployment Order

The deployment order is enforced by SSM parameter dependencies:
1. InfrastructureStack creates and exports SSM parameters
2. RagIngestionStack imports network resources from InfrastructureStack
3. InferenceApiStack imports network and shared table resources
4. AppApiStack imports all upstream resources

CDK will automatically detect the dependency order based on SSM parameter imports.

### Removal Policy Considerations

All shared tables use `getRemovalPolicy(config)` which returns:
- `RETAIN` for production environments (preserves data on stack deletion)
- `DESTROY` for dev/staging environments (allows clean teardown)

When moving tables from AppApiStack to InfrastructureStack, CloudFormation will:
1. Delete the table resource from AppApiStack (but retain the actual table due to RETAIN policy)
2. Import the existing table into InfrastructureStack (no data loss)

This is safe for production deployments.

### SSM Parameter Naming

All SSM parameter paths follow the convention:
```
/${projectPrefix}/{category}/{resource-name}
```

Categories:
- `/quota/` - Quota management tables
- `/cost-tracking/` - Cost tracking tables
- `/admin/` - Admin management tables
- `/auth/` - Authentication tables and secrets

This naming convention is preserved exactly to maintain compatibility with application code that reads these parameters.


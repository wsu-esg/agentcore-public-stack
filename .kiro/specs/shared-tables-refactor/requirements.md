# Requirements Document

## Introduction

The AgentCore Public Stack uses AWS CDK to define infrastructure across multiple stacks. Currently, `AppApiStack` creates 7 shared DynamoDB tables (UserQuotas, QuotaEvents, SessionsMetadata, UserCostSummary, SystemCostRollup, ManagedModels, AuthProviders) and a Secrets Manager resource (auth-provider-secrets) that are consumed by both `AppApiStack` and `InferenceApiStack`. Because `AppApiStack` also imports SSM parameters from `InferenceApiStack` and `RagIngestionStack`, a circular SSM parameter dependency exists that prevents deployment to a fresh AWS account.

This feature moves the shared DynamoDB tables and related resources from `AppApiStack` to `InfrastructureStack` (the foundation layer), breaking the circular dependency and enabling a clean linear deployment order: InfrastructureStack → RagIngestionStack → InferenceApiStack → AppApiStack.

## Glossary

- **InfrastructureStack**: The foundation CDK stack (`infrastructure/lib/infrastructure-stack.ts`) that creates VPC, ALB, ECS Cluster, and core DynamoDB tables. Deploys first with no upstream dependencies.
- **AppApiStack**: The backend service CDK stack (`infrastructure/lib/app-api-stack.ts`) that creates the ECS Fargate service for the App API and currently owns the shared tables.
- **InferenceApiStack**: The inference CDK stack (`infrastructure/lib/inference-api-stack.ts`) that creates AgentCore resources (Memory, Code Interpreter, Browser) and imports shared table ARNs via SSM.
- **RagIngestionStack**: The RAG ingestion CDK stack that creates the assistants table, documents bucket, and vector bucket resources consumed by AppApiStack.
- **Shared_Tables**: The 7 DynamoDB tables consumed by both AppApiStack and InferenceApiStack: UserQuotas, QuotaEvents, SessionsMetadata, UserCostSummary, SystemCostRollup, ManagedModels, AuthProviders.
- **SSM_Parameter**: An AWS Systems Manager Parameter Store entry used for cross-stack references, following the `/${projectPrefix}/...` naming convention.
- **Deployment_Order**: The sequence in which CDK stacks must be deployed: InfrastructureStack → RagIngestionStack → InferenceApiStack → AppApiStack.
- **Stack_Dependency_Graph**: A directed graph where an edge from StackA to StackB means StackB reads an SSM parameter that StackA writes.

## Requirements

### Requirement 1: Move Shared DynamoDB Tables to InfrastructureStack

**User Story:** As a DevOps engineer, I want shared DynamoDB tables created in the foundation layer, so that all consumer stacks can import them without circular dependencies.

#### Acceptance Criteria

1. WHEN the InfrastructureStack is deployed, THE InfrastructureStack SHALL create the UserQuotas DynamoDB table with partition key PK (String), sort key SK (String), PAY_PER_REQUEST billing, point-in-time recovery enabled, AWS_MANAGED encryption, and GSIs: AssignmentTypeIndex, UserAssignmentIndex, RoleAssignmentIndex, UserOverrideIndex, AppRoleAssignmentIndex
2. WHEN the InfrastructureStack is deployed, THE InfrastructureStack SHALL create the QuotaEvents DynamoDB table with partition key PK (String), sort key SK (String), PAY_PER_REQUEST billing, point-in-time recovery enabled, AWS_MANAGED encryption, and GSI: TierEventIndex
3. WHEN the InfrastructureStack is deployed, THE InfrastructureStack SHALL create the SessionsMetadata DynamoDB table with partition key PK (String), sort key SK (String), PAY_PER_REQUEST billing, point-in-time recovery enabled, AWS_MANAGED encryption, TTL attribute "ttl", and GSIs: UserTimestampIndex, SessionLookupIndex
4. WHEN the InfrastructureStack is deployed, THE InfrastructureStack SHALL create the UserCostSummary DynamoDB table with partition key PK (String), sort key SK (String), PAY_PER_REQUEST billing, point-in-time recovery enabled, AWS_MANAGED encryption, and GSI: PeriodCostIndex (with INCLUDE projection for userId, totalCost, totalRequests, lastUpdated)
5. WHEN the InfrastructureStack is deployed, THE InfrastructureStack SHALL create the SystemCostRollup DynamoDB table with partition key PK (String), sort key SK (String), PAY_PER_REQUEST billing, point-in-time recovery enabled, and AWS_MANAGED encryption
6. WHEN the InfrastructureStack is deployed, THE InfrastructureStack SHALL create the ManagedModels DynamoDB table with partition key PK (String), sort key SK (String), PAY_PER_REQUEST billing, point-in-time recovery enabled, AWS_MANAGED encryption, and GSI: ModelIdIndex
7. WHEN the InfrastructureStack is deployed, THE InfrastructureStack SHALL create the AuthProviders DynamoDB table with partition key PK (String), sort key SK (String), PAY_PER_REQUEST billing, point-in-time recovery enabled, AWS_MANAGED encryption, DynamoDB Stream (NEW_AND_OLD_IMAGES), and GSI: EnabledProvidersIndex
8. WHEN the InfrastructureStack is deployed, THE InfrastructureStack SHALL create the auth-provider-secrets Secrets Manager resource with RETAIN removal policy


### Requirement 2: Export Shared Table SSM Parameters from InfrastructureStack

**User Story:** As a DevOps engineer, I want shared table names and ARNs exported to SSM from InfrastructureStack, so that consumer stacks can import them using the existing parameter paths.

#### Acceptance Criteria

1. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameters for UserQuotas table at paths `/${projectPrefix}/quota/user-quotas-table-name` and `/${projectPrefix}/quota/user-quotas-table-arn`
2. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameters for QuotaEvents table at paths `/${projectPrefix}/quota/quota-events-table-name` and `/${projectPrefix}/quota/quota-events-table-arn`
3. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameters for SessionsMetadata table at paths `/${projectPrefix}/cost-tracking/sessions-metadata-table-name` and `/${projectPrefix}/cost-tracking/sessions-metadata-table-arn`
4. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameters for UserCostSummary table at paths `/${projectPrefix}/cost-tracking/user-cost-summary-table-name` and `/${projectPrefix}/cost-tracking/user-cost-summary-table-arn`
5. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameters for SystemCostRollup table at paths `/${projectPrefix}/cost-tracking/system-cost-rollup-table-name` and `/${projectPrefix}/cost-tracking/system-cost-rollup-table-arn`
6. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameters for ManagedModels table at paths `/${projectPrefix}/admin/managed-models-table-name` and `/${projectPrefix}/admin/managed-models-table-arn`
7. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameters for AuthProviders table at paths `/${projectPrefix}/auth/auth-providers-table-name` and `/${projectPrefix}/auth/auth-providers-table-arn`
8. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameters for AuthProviders stream ARN at path `/${projectPrefix}/auth/auth-providers-stream-arn`
9. WHEN the InfrastructureStack creates the shared tables, THE InfrastructureStack SHALL export SSM parameter for auth-provider-secrets ARN at path `/${projectPrefix}/auth/auth-provider-secrets-arn`

### Requirement 3: Remove Shared Table Definitions from AppApiStack

**User Story:** As a DevOps engineer, I want shared table definitions removed from AppApiStack, so that AppApiStack no longer creates resources that belong in the foundation layer.

#### Acceptance Criteria

1. WHEN the AppApiStack is deployed, THE AppApiStack SHALL import shared table names and ARNs via SSM parameters from InfrastructureStack instead of creating the 7 shared DynamoDB tables locally
2. WHEN the AppApiStack is deployed, THE AppApiStack SHALL import the auth-provider-secrets ARN via SSM parameter from InfrastructureStack instead of creating the Secrets Manager resource locally
3. WHEN the AppApiStack is deployed, THE AppApiStack SHALL use imported SSM values for ECS container environment variables that reference shared table names (DYNAMODB_QUOTA_TABLE, DYNAMODB_EVENTS_TABLE, DYNAMODB_MANAGED_MODELS_TABLE_NAME, DYNAMODB_SESSIONS_METADATA_TABLE_NAME, DYNAMODB_COST_SUMMARY_TABLE_NAME, DYNAMODB_SYSTEM_ROLLUP_TABLE_NAME, DYNAMODB_AUTH_PROVIDERS_TABLE_NAME, AUTH_PROVIDER_SECRETS_ARN)
4. WHEN the AppApiStack is deployed, THE AppApiStack SHALL grant the ECS task role the same DynamoDB read/write permissions on shared table ARNs using explicit IAM policy statements with imported ARNs
5. WHEN the AppApiStack is deployed, THE AppApiStack SHALL use `dynamodb.Table.fromTableAttributes()` to reconstruct the AuthProviders table reference for the RuntimeProvisioner Lambda DynamoDB Stream event source
6. WHEN the AppApiStack is deployed, THE AppApiStack SHALL grant the RuntimeProvisioner and RuntimeUpdater Lambda functions the same DynamoDB permissions on the AuthProviders table using imported ARNs

### Requirement 4: Eliminate Circular SSM Dependency

**User Story:** As a DevOps engineer, I want a valid linear deployment order with no circular dependencies, so that the stack can be deployed to a fresh AWS account without errors.

#### Acceptance Criteria

1. THE Stack_Dependency_Graph SHALL form a directed acyclic graph (DAG) with no cycles between any stacks
2. WHEN deploying to a fresh AWS account, THE Deployment_Order SHALL support InfrastructureStack → RagIngestionStack → InferenceApiStack → AppApiStack, where each stack only reads SSM parameters written by stacks earlier in the sequence
3. WHEN deploying InfrastructureStack first, THE InfrastructureStack SHALL create all shared tables and export SSM parameters before any consumer stack deploys
4. WHEN deploying InferenceApiStack after InfrastructureStack, THE InferenceApiStack SHALL successfully import shared table ARNs from SSM parameters created by InfrastructureStack
5. WHEN deploying AppApiStack after InfrastructureStack, RagIngestionStack, and InferenceApiStack, THE AppApiStack SHALL successfully import all required SSM parameters without encountering `ValidationError: Unable to fetch parameters`

### Requirement 5: Preserve Non-Shared Resources in AppApiStack

**User Story:** As a DevOps engineer, I want resources that are only used by AppApiStack to remain in AppApiStack, so that the refactor scope is minimal and non-shared resources stay in the correct layer.

#### Acceptance Criteria

1. THE AppApiStack SHALL continue to create and manage the Assistants DynamoDB table with GSIs: OwnerStatusIndex, VisibilityStatusIndex, SharedWithIndex
2. THE AppApiStack SHALL continue to create and manage the AssistantsDocumentsBucket S3 bucket
3. THE AppApiStack SHALL continue to create and manage the AssistantsVectorBucket S3 Vector Bucket and AssistantsVectorIndex
4. THE AppApiStack SHALL continue to create and manage the UserFiles DynamoDB table and UserFilesBucket S3 bucket
5. THE AppApiStack SHALL continue to create and manage the RuntimeProvisioner Lambda function and RuntimeUpdater Lambda function

### Requirement 6: Preserve Table Definitions Identically

**User Story:** As a DevOps engineer, I want moved table definitions to be identical to the originals, so that no data schema changes or behavioral differences are introduced.

#### Acceptance Criteria

1. FOR ALL shared DynamoDB tables moved to InfrastructureStack, THE InfrastructureStack SHALL use the same table names generated by `getResourceName(config, ...)` as the original AppApiStack definitions
2. FOR ALL shared DynamoDB tables moved to InfrastructureStack, THE InfrastructureStack SHALL use the same partition key schemas, sort key schemas, and attribute definitions as the original AppApiStack definitions
3. FOR ALL shared DynamoDB tables with GSIs, THE InfrastructureStack SHALL define the same GSI names, key schemas, and projection types (including nonKeyAttributes where applicable) as the original AppApiStack definitions
4. FOR ALL shared DynamoDB tables moved to InfrastructureStack, THE InfrastructureStack SHALL use the same billingMode (PAY_PER_REQUEST), pointInTimeRecovery, encryption (AWS_MANAGED), and removalPolicy settings as the original AppApiStack definitions
5. WHEN the AuthProviders table is moved, THE InfrastructureStack SHALL preserve the DynamoDB Stream configuration (NEW_AND_OLD_IMAGES)
6. WHEN the SessionsMetadata table is moved, THE InfrastructureStack SHALL preserve the TTL attribute ("ttl")
7. WHEN the PeriodCostIndex GSI on UserCostSummary is moved, THE InfrastructureStack SHALL preserve the INCLUDE projection type with nonKeyAttributes: userId, totalCost, totalRequests, lastUpdated

### Requirement 7: Preserve IAM Permissions and Environment Variables

**User Story:** As a DevOps engineer, I want IAM permissions and ECS environment variables to produce the same effective configuration after the refactor, so that backend application code is completely unaffected.

#### Acceptance Criteria

1. WHEN the AppApiStack ECS task role references shared tables, THE AppApiStack SHALL grant the same DynamoDB actions (GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteItem as applicable) on the same table ARNs and index ARNs as before the refactor
2. WHEN the InferenceApiStack runtime execution role references shared tables, THE InferenceApiStack SHALL continue to read the same SSM parameter paths for shared table ARNs and grant the same DynamoDB and Secrets Manager permissions
3. WHEN the AppApiStack ECS container is configured, THE AppApiStack SHALL pass the same table name values in environment variables as before the refactor
4. WHEN the RuntimeProvisioner Lambda references the AuthProviders table, THE AppApiStack SHALL grant the same DynamoDB Stream read permissions and DynamoDB read/write permissions using the imported table reference
5. WHEN the RuntimeUpdater Lambda references the AuthProviders table, THE AppApiStack SHALL grant the same DynamoDB read/write permissions using the imported table reference

### Requirement 8: Scope Changes to CDK Infrastructure Code Only

**User Story:** As a DevOps engineer, I want all changes confined to CDK infrastructure code, so that backend application code, frontend code, Lambda function code, and deployment scripts remain unchanged.

#### Acceptance Criteria

1. THE refactor SHALL modify only files within the `infrastructure/lib/` directory (CDK stack definitions)
2. THE refactor SHALL NOT modify any backend Python application code in `backend/src/`
3. THE refactor SHALL NOT modify any frontend Angular application code in `frontend/ai.client/`
4. THE refactor SHALL NOT modify any Lambda function code in `backend/lambda-functions/`
5. THE refactor SHALL NOT modify any deployment scripts in `scripts/` or GitHub Actions workflows in `.github/workflows/`

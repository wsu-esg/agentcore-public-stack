# Implementation Plan: Shared Tables Refactor

## Overview

This implementation plan refactors the CDK infrastructure to move 7 shared DynamoDB tables and the auth-provider-secrets Secrets Manager resource from AppApiStack to InfrastructureStack. This eliminates a circular SSM parameter dependency and establishes a clean linear deployment order: InfrastructureStack → RagIngestionStack → InferenceApiStack → AppApiStack.

All changes are confined to `infrastructure/lib/` directory. No application code, Lambda functions, deployment scripts, or workflows are modified. The refactor preserves all table schemas, GSI definitions, IAM permissions, and environment variables exactly as they exist today.

## Tasks

- [x] 1. Move shared DynamoDB tables to InfrastructureStack
  - [x] 1.1 Add UserQuotas table definition to InfrastructureStack
    - Copy table definition from AppApiStack with partition key PK, sort key SK, PAY_PER_REQUEST billing
    - Include all 5 GSIs: AssignmentTypeIndex, UserAssignmentIndex, RoleAssignmentIndex, UserOverrideIndex, AppRoleAssignmentIndex
    - Add SSM parameter exports for table name and ARN at `/${projectPrefix}/quota/user-quotas-table-name` and `/${projectPrefix}/quota/user-quotas-table-arn`
    - _Requirements: 1.1, 2.1, 6.1, 6.2, 6.3, 6.4_
  
  - [x] 1.2 Add QuotaEvents table definition to InfrastructureStack
    - Copy table definition from AppApiStack with partition key PK, sort key SK, PAY_PER_REQUEST billing
    - Include GSI: TierEventIndex
    - Add SSM parameter exports for table name and ARN at `/${projectPrefix}/quota/quota-events-table-name` and `/${projectPrefix}/quota/quota-events-table-arn`
    - _Requirements: 1.2, 2.2, 6.1, 6.2, 6.3, 6.4_
  
  - [x] 1.3 Add SessionsMetadata table definition to InfrastructureStack
    - Copy table definition from AppApiStack with partition key PK, sort key SK, PAY_PER_REQUEST billing
    - Include TTL attribute "ttl" configuration
    - Include GSIs: UserTimestampIndex, SessionLookupIndex
    - Add SSM parameter exports for table name and ARN at `/${projectPrefix}/cost-tracking/sessions-metadata-table-name` and `/${projectPrefix}/cost-tracking/sessions-metadata-table-arn`
    - _Requirements: 1.3, 2.3, 6.1, 6.2, 6.3, 6.4, 6.6_
  
  - [x] 1.4 Add UserCostSummary table definition to InfrastructureStack
    - Copy table definition from AppApiStack with partition key PK, sort key SK, PAY_PER_REQUEST billing
    - Include GSI: PeriodCostIndex with INCLUDE projection type and nonKeyAttributes: userId, totalCost, totalRequests, lastUpdated
    - Add SSM parameter exports for table name and ARN at `/${projectPrefix}/cost-tracking/user-cost-summary-table-name` and `/${projectPrefix}/cost-tracking/user-cost-summary-table-arn`
    - _Requirements: 1.4, 2.4, 6.1, 6.2, 6.3, 6.4, 6.7_
  
  - [x] 1.5 Add SystemCostRollup table definition to InfrastructureStack
    - Copy table definition from AppApiStack with partition key PK, sort key SK, PAY_PER_REQUEST billing
    - Add SSM parameter exports for table name and ARN at `/${projectPrefix}/cost-tracking/system-cost-rollup-table-name` and `/${projectPrefix}/cost-tracking/system-cost-rollup-table-arn`
    - _Requirements: 1.5, 2.5, 6.1, 6.2, 6.3, 6.4_
  
  - [x] 1.6 Add ManagedModels table definition to InfrastructureStack
    - Copy table definition from AppApiStack with partition key PK, sort key SK, PAY_PER_REQUEST billing
    - Include GSI: ModelIdIndex
    - Add SSM parameter exports for table name and ARN at `/${projectPrefix}/admin/managed-models-table-name` and `/${projectPrefix}/admin/managed-models-table-arn`
    - _Requirements: 1.6, 2.6, 6.1, 6.2, 6.3, 6.4_
  
  - [x] 1.7 Add AuthProviders table definition to InfrastructureStack
    - Copy table definition from AppApiStack with partition key PK, sort key SK, PAY_PER_REQUEST billing
    - Include DynamoDB Stream configuration (NEW_AND_OLD_IMAGES)
    - Include GSI: EnabledProvidersIndex
    - Add SSM parameter exports for table name, ARN, and stream ARN at `/${projectPrefix}/auth/auth-providers-table-name`, `/${projectPrefix}/auth/auth-providers-table-arn`, and `/${projectPrefix}/auth/auth-providers-stream-arn`
    - _Requirements: 1.7, 2.7, 2.8, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 2. Move auth-provider-secrets to InfrastructureStack
  - [x] 2.1 Add auth-provider-secrets Secrets Manager resource to InfrastructureStack
    - Copy Secrets Manager secret definition from AppApiStack with RETAIN removal policy
    - Add SSM parameter export for secret ARN at `/${projectPrefix}/auth/auth-provider-secrets-arn`
    - _Requirements: 1.8, 2.9_

- [x] 3. Update AppApiStack to import shared tables via SSM
  - [x] 3.1 Remove shared table definitions from AppApiStack
    - Remove UserQuotas, QuotaEvents, SessionsMetadata, UserCostSummary, SystemCostRollup, ManagedModels, AuthProviders table definitions
    - Remove auth-provider-secrets Secrets Manager resource definition
    - Remove SSM parameter exports for shared tables (now exported by InfrastructureStack)
    - _Requirements: 3.1, 3.2, 8.1_
  
  - [x] 3.2 Import shared table names via SSM in AppApiStack
    - Import UserQuotas table name from `/${projectPrefix}/quota/user-quotas-table-name`
    - Import QuotaEvents table name from `/${projectPrefix}/quota/quota-events-table-name`
    - Import SessionsMetadata table name from `/${projectPrefix}/cost-tracking/sessions-metadata-table-name`
    - Import UserCostSummary table name from `/${projectPrefix}/cost-tracking/user-cost-summary-table-name`
    - Import SystemCostRollup table name from `/${projectPrefix}/cost-tracking/system-cost-rollup-table-name`
    - Import ManagedModels table name from `/${projectPrefix}/admin/managed-models-table-name`
    - Import AuthProviders table name from `/${projectPrefix}/auth/auth-providers-table-name`
    - _Requirements: 3.1, 3.3_
  
  - [x] 3.3 Import shared table ARNs via SSM in AppApiStack
    - Import UserQuotas table ARN from `/${projectPrefix}/quota/user-quotas-table-arn`
    - Import QuotaEvents table ARN from `/${projectPrefix}/quota/quota-events-table-arn`
    - Import SessionsMetadata table ARN from `/${projectPrefix}/cost-tracking/sessions-metadata-table-arn`
    - Import UserCostSummary table ARN from `/${projectPrefix}/cost-tracking/user-cost-summary-table-arn`
    - Import SystemCostRollup table ARN from `/${projectPrefix}/cost-tracking/system-cost-rollup-table-arn`
    - Import ManagedModels table ARN from `/${projectPrefix}/admin/managed-models-table-arn`
    - Import AuthProviders table ARN from `/${projectPrefix}/auth/auth-providers-table-arn`
    - Import AuthProviders stream ARN from `/${projectPrefix}/auth/auth-providers-stream-arn`
    - Import auth-provider-secrets ARN from `/${projectPrefix}/auth/auth-provider-secrets-arn`
    - _Requirements: 3.1, 3.2_

- [x] 4. Update ECS task role IAM permissions in AppApiStack
  - [x] 4.1 Add explicit IAM policy for UserQuotas table access
    - Create IAM policy statement with actions: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteData
    - Include resources: table ARN and `${tableArn}/index/*` for GSI access
    - Add to ECS task role
    - _Requirements: 3.4, 7.1_
  
  - [x] 4.2 Add explicit IAM policy for QuotaEvents table access
    - Create IAM policy statement with actions: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteData
    - Include resources: table ARN and `${tableArn}/index/*` for GSI access
    - Add to ECS task role
    - _Requirements: 3.4, 7.1_
  
  - [x] 4.3 Add explicit IAM policy for SessionsMetadata table access
    - Create IAM policy statement with actions: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteData
    - Include resources: table ARN and `${tableArn}/index/*` for GSI access
    - Add to ECS task role
    - _Requirements: 3.4, 7.1_
  
  - [x] 4.4 Add explicit IAM policy for UserCostSummary table access
    - Create IAM policy statement with actions: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteData
    - Include resources: table ARN and `${tableArn}/index/*` for GSI access
    - Add to ECS task role
    - _Requirements: 3.4, 7.1_
  
  - [x] 4.5 Add explicit IAM policy for SystemCostRollup table access
    - Create IAM policy statement with actions: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteData
    - Include resources: table ARN and `${tableArn}/index/*` for GSI access
    - Add to ECS task role
    - _Requirements: 3.4, 7.1_
  
  - [x] 4.6 Add explicit IAM policy for ManagedModels table access
    - Create IAM policy statement with actions: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteData
    - Include resources: table ARN and `${tableArn}/index/*` for GSI access
    - Add to ECS task role
    - _Requirements: 3.4, 7.1_
  
  - [x] 4.7 Add explicit IAM policy for AuthProviders table access
    - Create IAM policy statement with actions: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteData
    - Include resources: table ARN and `${tableArn}/index/*` for GSI access
    - Add to ECS task role
    - _Requirements: 3.4, 7.1_
  
  - [x] 4.8 Add explicit IAM policy for auth-provider-secrets access
    - Create IAM policy statement with actions: secretsmanager:GetSecretValue
    - Include resource: secret ARN
    - Add to ECS task role
    - _Requirements: 3.4, 7.1_

- [x] 5. Update ECS container environment variables in AppApiStack
  - [x] 5.1 Update environment variables to use imported table names
    - Set DYNAMODB_QUOTA_TABLE to imported UserQuotas table name
    - Set DYNAMODB_EVENTS_TABLE to imported QuotaEvents table name
    - Set DYNAMODB_MANAGED_MODELS_TABLE_NAME to imported ManagedModels table name
    - Set DYNAMODB_SESSIONS_METADATA_TABLE_NAME to imported SessionsMetadata table name
    - Set DYNAMODB_COST_SUMMARY_TABLE_NAME to imported UserCostSummary table name
    - Set DYNAMODB_SYSTEM_ROLLUP_TABLE_NAME to imported SystemCostRollup table name
    - Set DYNAMODB_AUTH_PROVIDERS_TABLE_NAME to imported AuthProviders table name
    - Set AUTH_PROVIDER_SECRETS_ARN to imported secret ARN
    - _Requirements: 3.3, 7.3_

- [x] 6. Update RuntimeProvisioner Lambda in AppApiStack
  - [x] 6.1 Reconstruct AuthProviders table reference using fromTableAttributes
    - Use dynamodb.Table.fromTableAttributes() with imported table name, ARN, and stream ARN
    - Store reconstructed table reference for event source and IAM grants
    - _Requirements: 3.5, 7.4_
  
  - [x] 6.2 Update RuntimeProvisioner Lambda DynamoDB Stream event source
    - Add DynamoDB Stream event source using reconstructed AuthProviders table reference
    - Configure with startingPosition: LATEST, batchSize: 1, retryAttempts: 3, bisectBatchOnError: true
    - _Requirements: 3.5, 7.4_
  
  - [x] 6.3 Grant RuntimeProvisioner Lambda permissions on AuthProviders table
    - Use reconstructed table reference to grant stream read permissions
    - Use reconstructed table reference to grant read/write data permissions
    - _Requirements: 3.6, 7.4_

- [x] 7. Update RuntimeUpdater Lambda in AppApiStack
  - [x] 7.1 Grant RuntimeUpdater Lambda permissions on AuthProviders table
    - Add explicit IAM policy statement with actions: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan
    - Include resources: imported AuthProviders table ARN and `${tableArn}/index/*`
    - _Requirements: 3.6, 7.5_

- [x] 8. Checkpoint - Synthesize and compare CloudFormation templates
  - Synthesize InfrastructureStack and AppApiStack templates
  - Verify InfrastructureStack adds 7 tables, 1 secret, and 9 SSM parameters
  - Verify AppApiStack removes 7 tables, 1 secret, and 9 SSM parameters
  - Verify AppApiStack adds SSM imports and explicit IAM policies
  - Ensure all tests pass, ask the user if questions arise
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

## Notes

- All changes are confined to `infrastructure/lib/infrastructure-stack.ts` and `infrastructure/lib/app-api-stack.ts`
- No changes to backend application code, Lambda functions, deployment scripts, or workflows
- Table schemas, GSI definitions, billing modes, and encryption settings are preserved exactly
- SSM parameter paths remain unchanged for backward compatibility
- Deployment order becomes: InfrastructureStack → RagIngestionStack → InferenceApiStack → AppApiStack
- Non-shared resources (Assistants, UserFiles, Lambda functions) remain in AppApiStack
- Use `getResourceName(config, ...)` for table names and `getRemovalPolicy(config)` for removal policies
- InferenceApiStack requires no changes (already imports via SSM, just update comments)

# Requirements Document

## Introduction

This feature automates the initial application bootstrap and data seeding process via GitHub Actions. Currently, first-time deployments leave the application in an unconfigured state — no auth providers, no quota tiers, no quota assignments, and no registered Bedrock models. Users see a manual setup guide on the login page and must run scripts by hand. This feature replaces that manual process with a CI/CD-driven seeding workflow that runs after infrastructure deployment, pulling configuration from GitHub Actions secrets/variables and applying sensible defaults for non-sensitive data.

## Glossary

- **Seed_Workflow**: The GitHub Actions workflow (`bootstrap-data-seeding.yml`) that orchestrates all data seeding jobs
- **Seed_Script**: A Python script (`backend/scripts/seed_bootstrap_data.py`) that writes seed data to DynamoDB and Secrets Manager
- **Auth_Provider_Seeder**: The component within the Seed_Script responsible for seeding OIDC authentication provider configuration into the auth-providers DynamoDB table and client secrets into Secrets Manager
- **Quota_Seeder**: The component within the Seed_Script responsible for seeding default quota tiers and quota assignments into the user-quotas DynamoDB table
- **Model_Seeder**: The component within the Seed_Script responsible for seeding default Bedrock model registrations into the managed-models DynamoDB table
- **Bootstrap_Scripts**: Shell scripts in `scripts/stack-bootstrap/` that wrap the Seed_Script invocation following the project's Shell Scripts First philosophy
- **DynamoDB_Auth_Providers_Table**: The DynamoDB table storing OIDC authentication provider configurations (PK/SK pattern: `AUTH_PROVIDER#{id}`)
- **DynamoDB_User_Quotas_Table**: The DynamoDB table storing quota tiers (PK: `TIER#{id}`) and quota assignments (PK: `ASSIGNMENT#{id}`)
- **DynamoDB_Managed_Models_Table**: The DynamoDB table storing registered Bedrock model configurations
- **Secrets_Manager_Auth_Secret**: The AWS Secrets Manager secret storing OIDC client secrets as a JSON map of `{provider_id: secret}`
- **SSM_Parameter_Store**: AWS Systems Manager Parameter Store, used to resolve DynamoDB table names and Secrets Manager ARNs at runtime via the `/${projectPrefix}/...` convention

## Requirements

### Requirement 1: Auth Provider Seeding via CI/CD

**User Story:** As a platform operator, I want the first OIDC auth provider to be automatically seeded during deployment, so that users can sign in immediately after the initial deploy without manual script execution.

#### Acceptance Criteria

1. WHEN the Seed_Workflow is triggered and auth provider GitHub secrets are configured, THE Auth_Provider_Seeder SHALL write the OIDC provider configuration to the DynamoDB_Auth_Providers_Table using the same item schema as the existing `seed_auth_provider.py` script
2. WHEN the Seed_Workflow is triggered and auth provider GitHub secrets are configured, THE Auth_Provider_Seeder SHALL store the OIDC client secret in the Secrets_Manager_Auth_Secret under the provider ID key
3. WHEN the `--discover` flag is enabled, THE Auth_Provider_Seeder SHALL fetch OIDC endpoints from the issuer URL's `.well-known/openid-configuration` endpoint and populate authorization, token, JWKS, userinfo, and end-session endpoints
4. IF the auth provider already exists in the DynamoDB_Auth_Providers_Table, THEN THE Auth_Provider_Seeder SHALL skip the write and log that the provider was already seeded
5. IF required auth provider secrets (issuer URL, client ID, client secret) are not configured in GitHub, THEN THE Seed_Workflow SHALL skip auth provider seeding and log a warning indicating which values are missing
6. THE Auth_Provider_Seeder SHALL read DynamoDB table names and Secrets Manager ARNs from SSM_Parameter_Store using the `/${projectPrefix}/auth/...` parameter paths

### Requirement 2: Default Quota Tier Seeding

**User Story:** As a platform operator, I want default quota tiers seeded automatically on first deploy, so that users have reasonable usage limits out of the box without manual admin configuration.

#### Acceptance Criteria

1. WHEN the Seed_Workflow is triggered, THE Quota_Seeder SHALL create a default quota tier in the DynamoDB_User_Quotas_Table with a PK of `TIER#{tier_id}` and SK of `TIER#{tier_id}`
2. THE Quota_Seeder SHALL seed the default tier with a monthly cost limit, a soft limit percentage of 80%, and an action-on-limit of "block"
3. IF a quota tier with the same tier ID already exists in the DynamoDB_User_Quotas_Table, THEN THE Quota_Seeder SHALL skip the write and log that the tier was already seeded
4. THE Quota_Seeder SHALL use sensible hardcoded defaults for quota tier values, requiring no GitHub secrets or variables for this data

### Requirement 3: Default Quota Assignment Seeding

**User Story:** As a platform operator, I want a default quota assignment seeded automatically, so that all users are assigned a quota tier without requiring per-user admin action.

#### Acceptance Criteria

1. WHEN the Seed_Workflow is triggered, THE Quota_Seeder SHALL create a default quota assignment in the DynamoDB_User_Quotas_Table with assignment type `default_tier` and priority 100
2. THE Quota_Seeder SHALL link the default assignment to the default quota tier created in Requirement 2
3. IF a quota assignment with the same assignment ID already exists in the DynamoDB_User_Quotas_Table, THEN THE Quota_Seeder SHALL skip the write and log that the assignment was already seeded
4. THE Quota_Seeder SHALL use sensible hardcoded defaults for assignment values, requiring no GitHub secrets or variables for this data

### Requirement 4: Default Bedrock Model Registration

**User Story:** As a platform operator, I want default Bedrock models pre-registered on first deploy, so that users can start conversations immediately without an admin manually adding models.

#### Acceptance Criteria

1. WHEN the Seed_Workflow is triggered, THE Model_Seeder SHALL create model registrations in the DynamoDB_Managed_Models_Table for a set of default Bedrock models (Claude Haiku and Claude Sonnet at minimum)
2. THE Model_Seeder SHALL populate each model registration with model ID, model name, provider, input/output modalities, token limits, pricing per million tokens, cache pricing, and caching support flag
3. THE Model_Seeder SHALL mark exactly one model as the default model for new sessions
4. IF a model with the same model ID already exists in the DynamoDB_Managed_Models_Table, THEN THE Model_Seeder SHALL skip the write and log that the model was already seeded
5. THE Model_Seeder SHALL use sensible hardcoded defaults for model configuration, requiring no GitHub secrets or variables for this data
6. THE Model_Seeder SHALL set `allowedAppRoles` and `availableToRoles` to empty lists so all users can access the default models

### Requirement 5: GitHub Actions Workflow Integration

**User Story:** As a platform operator, I want the seeding process integrated into the CI/CD pipeline, so that bootstrap data is applied automatically after infrastructure deployment.

#### Acceptance Criteria

1. THE Seed_Workflow SHALL be defined as a GitHub Actions workflow file at `.github/workflows/bootstrap-data-seeding.yml`
2. THE Seed_Workflow SHALL support `workflow_dispatch` for manual triggering with an environment input
3. THE Seed_Workflow SHALL support being called after infrastructure and App API deployments via `workflow_call` or manual dispatch
4. THE Seed_Workflow SHALL read auth provider configuration from GitHub secrets for sensitive values (client ID, client secret, secrets ARN) and GitHub variables for non-sensitive values (provider ID, display name, issuer URL, button color)
5. THE Seed_Workflow SHALL delegate all logic to shell scripts in `scripts/stack-bootstrap/` following the Shell Scripts First philosophy
6. THE Seed_Workflow SHALL source `scripts/common/load-env.sh` to resolve the project prefix and AWS configuration

### Requirement 6: Shell Scripts First Architecture

**User Story:** As a developer, I want the seeding logic in shell scripts rather than workflow YAML, so that I can run and test the seeding process locally.

#### Acceptance Criteria

1. THE Bootstrap_Scripts SHALL include a `scripts/stack-bootstrap/seed.sh` script that invokes the Seed_Script with appropriate environment variables
2. THE Bootstrap_Scripts SHALL include a `scripts/stack-bootstrap/install.sh` script that installs Python dependencies needed by the Seed_Script
3. THE Bootstrap_Scripts SHALL use `set -euo pipefail` for error handling
4. THE Bootstrap_Scripts SHALL be executable locally by sourcing `scripts/common/load-env.sh` and setting the required environment variables
5. THE Bootstrap_Scripts SHALL resolve DynamoDB table names and Secrets Manager ARNs from SSM_Parameter_Store using the project prefix convention

### Requirement 7: Idempotent Seeding

**User Story:** As a platform operator, I want the seeding process to be safely re-runnable, so that re-deploying or re-triggering the workflow does not corrupt or duplicate existing data.

#### Acceptance Criteria

1. THE Seed_Script SHALL check for existing records before writing each seed item
2. WHEN a seed item already exists, THE Seed_Script SHALL skip the write and log a message indicating the item was already present
3. THE Seed_Script SHALL complete successfully (exit code 0) even when all items are already seeded
4. FOR ALL seed operations, running the Seed_Script twice with identical inputs SHALL produce the same database state as running the Seed_Script once (idempotence property)

### Requirement 8: Observability and Error Handling

**User Story:** As a platform operator, I want clear logging and error reporting from the seeding process, so that I can diagnose failures during deployment.

#### Acceptance Criteria

1. THE Seed_Script SHALL log the outcome of each seed operation (created, skipped, or failed) with the item type and identifier
2. IF a DynamoDB or Secrets Manager write fails, THEN THE Seed_Script SHALL log the error details and exit with a non-zero exit code
3. IF OIDC discovery fails for the auth provider, THEN THE Seed_Script SHALL log a warning and continue seeding with manually provided or default endpoint values
4. THE Seed_Script SHALL produce a summary at completion listing the count of items created, skipped, and failed for each data category (auth providers, quota tiers, quota assignments, models)

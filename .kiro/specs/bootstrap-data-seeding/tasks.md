# Implementation Plan: Bootstrap Data Seeding

## Overview

Automate post-deployment bootstrap data seeding via a unified Python script invoked by GitHub Actions. The implementation follows the project's Shell Scripts First philosophy, with shell wrappers in `scripts/stack-bootstrap/` delegating to `backend/scripts/seed_bootstrap_data.py`. The script seeds auth providers, quota tiers, quota assignments, and Bedrock models into DynamoDB, with idempotent check-before-write logic and structured summary reporting.

## Tasks

- [x] 1. Create the Python seed script with core data structures and entry point
  - [x] 1.1 Create `backend/scripts/seed_bootstrap_data.py` with `SeedResult` dataclass, logging setup, and `main()` entry point that reads environment variables and dispatches to seeder functions
    - Define `SeedResult` with `category`, `created`, `skipped`, `failed`, `details` fields
    - `main()` reads env vars (`SEED_AUTH_*`, `DDB_AUTH_PROVIDERS_TABLE`, `DDB_USER_QUOTAS_TABLE`, `DDB_MANAGED_MODELS_TABLE`, `SECRETS_AUTH_ARN`, `AWS_REGION`), calls each seeder, collects results, prints summary, exits non-zero if any failures
    - Skip auth provider seeding if `SEED_AUTH_ISSUER_URL`, `SEED_AUTH_CLIENT_ID`, or `SEED_AUTH_CLIENT_SECRET` are missing, log warning listing which are absent
    - _Requirements: 1.5, 7.3, 8.1, 8.2, 8.4_

  - [x] 1.2 Implement `seed_auth_provider()` function
    - Accept `table_name`, `secrets_arn`, `region`, `provider_id`, `display_name`, `issuer_url`, `client_id`, `client_secret`, `button_color`, `discover` parameters
    - Check for existing item via `get_item` on PK/SK `AUTH_PROVIDER#{provider_id}` — skip if exists
    - If `discover=True`, fetch `{issuer_url}/.well-known/openid-configuration` via `httpx`, map `authorization_endpoint`, `token_endpoint`, `jwks_uri`, `userinfo_endpoint`, `end_session_endpoint` to DynamoDB fields; on failure log warning and continue
    - Write DynamoDB item matching the schema in the design (all required fields, `createdBy: bootstrap-seed`)
    - Read existing Secrets Manager JSON, add `{provider_id: client_secret}` key if not present, write back
    - Return `SeedResult` with counts
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 8.3_

  - [x] 1.3 Implement `seed_default_quota_tier()` function
    - Write default tier item with PK=`QUOTA_TIER#default`, SK=`METADATA`, $50 monthly limit, 80% soft limit, block action
    - Check for existing item via `get_item` — skip if exists
    - Return `SeedResult`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 1.4 Implement `seed_default_quota_assignment()` function
    - Write default assignment item with PK=`ASSIGNMENT#default-assignment`, SK=`METADATA`, type `default_tier`, priority 100, linked to `default` tier
    - Check for existing item via `get_item` — skip if exists
    - Return `SeedResult`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 1.5 Implement `seed_default_models()` function
    - Seed Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`, `isDefault=True`) and Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`, `isDefault=False`)
    - Use `uuid5` with a fixed namespace for deterministic UUIDs from model IDs
    - Query `GSI1PK = MODEL#{modelId}` to check existence — skip if exists
    - Set `allowedAppRoles` and `availableToRoles` to empty lists
    - Populate all pricing, token limit, modality, and caching fields per design
    - Return `SeedResult`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 2. Checkpoint — Verify seed script runs locally
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Create shell scripts in `scripts/stack-bootstrap/`
  - [x] 3.1 Create `scripts/stack-bootstrap/install.sh`
    - Use `set -euo pipefail`
    - Install Python dependencies: `boto3`, `httpx`
    - _Requirements: 6.2, 6.3_

  - [x] 3.2 Create `scripts/stack-bootstrap/seed.sh`
    - Use `set -euo pipefail`
    - Source `scripts/common/load-env.sh`
    - Resolve DynamoDB table names and Secrets Manager ARN from SSM using `aws ssm get-parameter` with `/${projectPrefix}/auth/auth-providers-table-name`, `/${projectPrefix}/auth/auth-provider-secrets-arn`, `/${projectPrefix}/quota/user-quotas-table-name`, `/${projectPrefix}/admin/managed-models-table-name`
    - Export resolved values as environment variables and invoke `python backend/scripts/seed_bootstrap_data.py`
    - _Requirements: 6.1, 6.3, 6.4, 6.5_

- [x] 4. Create GitHub Actions workflow
  - [x] 4.1 Create `.github/workflows/bootstrap-data-seeding.yml`
    - Define `workflow_dispatch` trigger with `environment` input
    - Define `workflow_call` trigger for chaining after infrastructure deploys
    - Read auth config from GitHub secrets (`SEED_AUTH_CLIENT_ID`, `SEED_AUTH_CLIENT_SECRET`) and variables (`SEED_AUTH_PROVIDER_ID`, `SEED_AUTH_DISPLAY_NAME`, `SEED_AUTH_ISSUER_URL`, `SEED_AUTH_BUTTON_COLOR`, `CDK_PROJECT_PREFIX`, `AWS_REGION`)
    - Single job: checkout, configure AWS credentials, run `scripts/stack-bootstrap/install.sh`, run `scripts/stack-bootstrap/seed.sh`
    - Pass all `SEED_AUTH_*` and `CDK_*` env vars to the seed step
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 5. Checkpoint — Verify workflow and scripts are wired correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Write tests
  - [ ] 6.1 Create test file `backend/tests/scripts/test_seed_bootstrap_data.py` with pytest fixtures using `moto` to mock DynamoDB tables and Secrets Manager, and `respx` or `httpx` mock for OIDC discovery
    - Create DynamoDB tables matching production schemas (auth-providers, user-quotas, managed-models with GSIs)
    - Create Secrets Manager secret with empty JSON `{}`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 6.2 Write unit tests for auth provider seeding
    - Test successful auth provider creation with all fields present
    - Test idempotent skip when provider already exists
    - Test missing env vars triggers skip with warning
    - Test OIDC discovery failure logs warning and continues
    - Test secret storage adds provider key to existing JSON
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 8.3_

  - [ ] 6.3 Write unit tests for quota seeding
    - Test default tier has $50 monthly limit, 80% soft limit, block action
    - Test default assignment has `default_tier` type, priority 100, linked to `default` tier
    - Test idempotent skip for both tier and assignment
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

  - [ ] 6.4 Write unit tests for model seeding
    - Test Haiku 4.5 is marked as default, Sonnet 4.6 is not
    - Test both models use global inference profile IDs (`us.anthropic.*`)
    - Test `allowedAppRoles` and `availableToRoles` are empty lists
    - Test deterministic UUID generation is consistent across runs
    - Test idempotent skip when models already exist
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ] 6.5 Write unit tests for summary reporting
    - Test summary includes counts for all four categories
    - Test exit code 0 when all items created or all skipped
    - Test exit code 1 when any operation fails
    - _Requirements: 8.1, 8.2, 8.4_

  - [ ] 6.6 Write property test: Auth provider item schema correctness (Property 1)
    - **Property 1: Auth provider item schema correctness**
    - Generate random valid provider configs via Hypothesis, verify DynamoDB item has correct PK/SK pattern and all required fields
    - **Validates: Requirements 1.1**

  - [ ] 6.7 Write property test: Secret storage round-trip (Property 2)
    - **Property 2: Secret storage round-trip**
    - Generate random provider IDs and secrets, verify round-trip through mocked Secrets Manager
    - **Validates: Requirements 1.2**

  - [ ] 6.8 Write property test: OIDC discovery endpoint mapping (Property 3)
    - **Property 3: OIDC discovery endpoint mapping**
    - Generate random discovery response dicts, verify field name mapping to DynamoDB item fields
    - **Validates: Requirements 1.3**

  - [ ] 6.9 Write property test: Seed idempotence (Property 4)
    - **Property 4: Seed idempotence**
    - Generate random valid seed configs, run seeder twice against mocked DynamoDB, verify identical state and second run has created=0
    - **Validates: Requirements 1.4, 2.3, 3.3, 4.4, 7.1, 7.2, 7.4**

  - [ ] 6.10 Write property test: Model registration field completeness (Property 5)
    - **Property 5: Model registration field completeness**
    - Verify all default models have every required field present
    - **Validates: Requirements 4.2, 4.6**

  - [ ] 6.11 Write property test: Exactly one default model invariant (Property 6)
    - **Property 6: Exactly one default model invariant**
    - Run model seeder against mocked DynamoDB, count items with `isDefault=True`, assert exactly one
    - **Validates: Requirements 4.3**

  - [ ] 6.12 Write property test: Summary accuracy (Property 7)
    - **Property 7: Summary accuracy**
    - Generate random pre-existing states, run seeder, verify `created + skipped + failed` equals total items attempted per category
    - **Validates: Requirements 8.1, 8.4**

- [ ] 7. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The design uses Python explicitly — all implementation code is Python 3.13+ with `boto3` and `httpx`
- Shell scripts follow `set -euo pipefail` and the Shell Scripts First philosophy
- Property tests use `hypothesis` with `@settings(max_examples=100)` and `moto` for AWS mocking
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation

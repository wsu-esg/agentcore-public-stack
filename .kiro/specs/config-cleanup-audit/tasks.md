# Implementation Plan: Config Cleanup Audit

## Overview

Systematic removal of dead configuration, consolidation of duplicates, enforcement of the config default hierarchy, and documentation of the final state. Changes are organized to minimize merge conflicts: structural changes to config.ts first, then dead code removal across layers, then consolidation, then validation and docs.

All runtime commands must execute inside the Docker container (`docker compose exec dev <command>`).

## Tasks

- [x] 1. Enforce config default hierarchy — move all hardcoded defaults to cdk.context.json
  - [x] 1.1 Remove hardcoded fallback defaults from `loadConfig()` in `infrastructure/lib/config.ts`
    - Remove trailing `|| <literal>` and second arguments to `parseBooleanEnv()` / `parseIntEnv()` that act as defaults
    - Retain empty-string fallbacks (`|| ''`) for `imageTag` and `ragIngestion.corsOrigins` as "not set" sentinels
    - Each field reads env var first, then `scope.node.tryGetContext()`, with no hardcoded default
    - _Requirements: 17.1, 17.2, 17.5_

  - [x] 1.2 Add all default values to `cdk.context.json`
    - Add `production: true`, `retainDataOnDelete: false` at top level
    - Add `fileUpload.enabled: true`, `fileUpload.maxFileSizeBytes: 4194304`, `fileUpload.maxFilesPerMessage: 5`, `fileUpload.userQuotaBytes: 1073741824`, `fileUpload.retentionDays: 365`
    - Add `assistants.enabled: true`
    - Add `ragIngestion.enabled: true`, `ragIngestion.lambdaMemorySize: 10240`, `ragIngestion.lambdaTimeout: 900`, `ragIngestion.embeddingModel: "amazon.titan-embed-text-v2"`, `ragIngestion.vectorDimension: 1024`, `ragIngestion.vectorDistanceMetric: "cosine"`
    - _Requirements: 16.1, 17.2, 17.6_

  - [x] 1.3 Remove hardcoded bash defaults from `scripts/common/load-env.sh`
    - Remove `:-true`, `:-http://localhost:4200`, `:-10` and similar bash defaults
    - Each variable falls back to `get_json_value` from the context file
    - _Requirements: 17.3, 17.4_

- [x] 2. Remove dead config fields from CDK interfaces and context
  - [x] 2.1 Remove RDS fields from `AppApiConfig` interface and `loadConfig()` in `config.ts`
    - Remove `enableRds`, `rdsInstanceClass`, `rdsEngine`, `rdsDatabaseName` from interface and loader
    - _Requirements: 1.1, 1.3_

  - [x] 2.2 Remove `databaseType` from `AppApiConfig` interface and `loadConfig()` in `config.ts`
    - _Requirements: 5.1, 5.3_

  - [x] 2.3 Remove GPU field from `InferenceApiConfig` interface and `loadConfig()` in `config.ts`
    - Remove `enableGpu` from interface and loader
    - _Requirements: 2.1, 2.3_

  - [x] 2.4 Remove directory fields from `InferenceApiConfig` interface and `loadConfig()` in `config.ts`
    - Remove `uploadDir`, `outputDir`, `generatedImagesDir` from interface and loader
    - _Requirements: 4.1_

  - [x] 2.5 Remove `oauthCallbackUrl` from `InferenceApiConfig` interface and `loadConfig()` in `config.ts`
    - _Requirements: 18.1, 18.2_

  - [x] 2.6 Remove `enableRoute53` from `FrontendConfig` interface and `loadConfig()` in `config.ts`
    - _Requirements: 10.1, 10.4_

  - [x] 2.7 Remove all corresponding dead keys from `cdk.context.json`
    - Remove RDS keys (`enableRds`, `rdsInstanceClass`, `rdsEngine`, `rdsDatabaseName`) from `appApi` section
    - Remove `databaseType` from `appApi` section
    - Remove `enableGpu`, `uploadDir`, `outputDir`, `generatedImagesDir`, `oauthCallbackUrl` from `inferenceApi` section
    - Remove `enableRoute53` from `frontend` section
    - Remove `entraClientId`, `entraTenantId` if present
    - _Requirements: 1.2, 2.2, 4.2, 5.2, 8.5, 10.2, 11.4, 18.4_

  - [x] 2.8 Remove dead field exports from `scripts/common/load-env.sh`
    - Remove exports and context param blocks for: GPU, directory fields, oauthCallbackUrl, enableRoute53, databaseType, RDS fields
    - _Requirements: 10.4, 18.3_

- [x] 3. Remove ENABLE_AUTHENTICATION toggle entirely
  - [x] 3.1 Remove auth bypass from backend `dependencies.py`
    - Remove `ENABLE_AUTHENTICATION` env var check, `_check_auth_bypass()`, `_create_anonymous_dev_user()`
    - Remove `bypass_user = _check_auth_bypass()` calls from `get_current_user` and `get_current_user_trusted`
    - Authentication is always enforced
    - _Requirements: 14.1, 14.2_

  - [x] 3.2 Remove `ENABLE_AUTHENTICATION` from backend `jwt_validator.py`
    - Remove the env var check
    - _Requirements: 14.3_

  - [x] 3.3 Remove `ENABLE_AUTHENTICATION` log line from `inference_api/main.py`
    - _Requirements: 14.4_

  - [x] 3.4 Remove `ENABLE_AUTHENTICATION` from `.env.example`
    - _Requirements: 14.5_

  - [x] 3.5 Remove `enableAuthentication` from frontend `ConfigService`, `RuntimeConfig`, and computed signals
    - _Requirements: 14.6_

  - [x] 3.6 Remove `enableAuthentication` from `environment.ts` and `environment.production.ts`
    - _Requirements: 14.7_

  - [x] 3.7 Update frontend components to remove auth conditional bypass paths
    - Update auth guard, admin guard, auth interceptor, auth service, user service, chat-http service
    - Remove `config.enableAuthentication()` checks — auth is always on
    - _Requirements: 14.8_

  - [x] 3.8 Remove `CDK_ENABLE_AUTHENTICATION` and `ENV_INFERENCE_API_ENABLE_AUTHENTICATION` from GitHub Actions workflows, `load-env.sh`, `config.ts` InferenceApiConfig, and `ACTIONS-REFERENCE.md`
    - _Requirements: 14.9, 14.10_

  - [x] 3.9 Remove `ENABLE_AUTHENTICATION` sed replacement from `scripts/stack-frontend/build.sh`
    - _Requirements: 14.11_

  - [x] 3.10 Update `backend/src/apis/shared/auth/README.md` to remove ENABLE_AUTHENTICATION docs and stale Entra env var references
    - _Requirements: 14.12_

- [x] 4. Remove static inferenceApiUrl configuration
  - [x] 4.1 Remove `inferenceApiUrl` from frontend `RuntimeConfig` interface, computed signal, and `encodeUrlPath` helper in `ConfigService`
    - _Requirements: 15.1, 15.2_

  - [x] 4.2 Remove `inferenceApiUrl` from `environment.ts` and `environment.production.ts`
    - _Requirements: 15.3, 15.4_

  - [x] 4.3 Update `config.service.spec.ts` to remove `inferenceApiUrl` test cases
    - _Requirements: 15.5_

  - [x] 4.4 Remove static `inferenceApiUrl` fallback from `chat-http.service.ts`
    - The `!config.enableAuthentication()` path is already removed by task 3.7; remove any remaining static fallback
    - _Requirements: 15.6_

  - [x] 4.5 Update `preview-chat.service.ts` to resolve runtime endpoint dynamically via `authApiService.getRuntimeEndpoint()`
    - _Requirements: 15.7_

  - [x] 4.6 Remove `inferenceApiUrl` from CDK frontend stack `config.json` generation if present
    - _Requirements: 15.8_

  - [x] 4.7 Remove dead `apiUrl` and `frontendUrl` fields from `InferenceApiConfig` in `config.ts` and `cdk.context.json`
    - _Requirements: 15.9_

  - [x] 4.8 Remove inference API URL entries from `.env.example` and `ACTIONS-REFERENCE.md`
    - _Requirements: 15.10, 15.11_

- [x] 5. Checkpoint — compile and verify after major removals
  - Ensure TypeScript compiles cleanly: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/infrastructure && npx tsc --noEmit"`
  - Ensure CDK synth works: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/infrastructure && npx cdk synth --quiet"`
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Consolidate CORS origins to a single top-level field
  - [x] 6.1 Add `corsOrigins` field to `AppConfig` interface in `config.ts`
    - Define a single top-level `corsOrigins` in the `AppConfig` interface
    - Load from env var / context with fallback chain
    - _Requirements: 3.1_

  - [x] 6.2 Update stacks to use top-level `corsOrigins` as default, with per-section override
    - Each section that consumes CORS falls back to `config.corsOrigins` if its own `corsOrigins` is not set
    - _Requirements: 3.2, 3.3, 3.5_

  - [x] 6.3 Update `cdk.context.json` with single top-level `corsOrigins` and remove duplicated per-section values
    - Remove `corsOrigins` from `fileUpload`, `assistants`, `ragIngestion` sections (keep `inferenceApi.corsOrigins` if it differs)
    - Add top-level `corsOrigins`
    - _Requirements: 3.4_

  - [x] 6.4 Update `load-env.sh` to export a single `CDK_CORS_ORIGINS` and remove per-section CORS exports where redundant
    - _Requirements: 3.4_

- [x] 7. Update frontend stack for Route53 derivation
  - [x] 7.1 Change Route53 condition in frontend stack from `config.frontend.enableRoute53 && config.domainName` to `config.domainName`
    - _Requirements: 10.3_

  - [x] 7.2 Update CDK infrastructure tests to remove `enableRoute53` from test context setup
    - _Requirements: 10.5_

- [x] 8. Synchronize .env.example with actual usage
  - [x] 8.1 Audit all `os.getenv` / `os.environ` calls in `backend/src/` and cross-reference with `.env.example`
    - Remove entries from `.env.example` that are not referenced by any Python module
    - Verify loaded values have meaningful downstream usage; remove dead loads
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 8.2 Add section headers and comments to `.env.example` for clarity
    - Group related variables under labeled sections
    - Add comments for `UPLOAD_DIR`, `OUTPUT_DIR`, `GENERATED_IMAGES_DIR` clarifying they are local-dev-only
    - _Requirements: 4.4, 6.5_

- [x] 9. Remove dead frontend environment imports
  - [x] 9.1 Find and remove unused `environment` imports from Angular source files
    - Only `ConfigService` should import from `environments/environment`
    - _Requirements: 7.1, 7.2_

- [x] 10. Remove stale Entra ID configuration remnants
  - [x] 10.1 Remove `entraClientId`, `entraTenantId`, `entraRedirectUri` from CDK infrastructure test context setup
    - _Requirements: 11.1_

  - [x] 10.2 Update `.github/ACTIONS-REFERENCE.md` to remove Entra-specific entries
    - Remove `CDK_ENTRA_CLIENT_ID`, `CDK_ENTRA_TENANT_ID`, `CDK_APP_API_ENTRA_REDIRECT_URI`
    - _Requirements: 11.2_

  - [x] 10.3 Update `.github/README-ACTIONS.md` to replace Entra-specific auth guidance with generic OIDC reference
    - _Requirements: 11.3_

- [x] 11. Migrate non-sensitive GitHub Secrets to Variables
  - [x] 11.1 Change `secrets.CDK_AWS_ACCOUNT`, `secrets.CDK_FRONTEND_CERTIFICATE_ARN`, `secrets.CDK_FRONTEND_BUCKET_NAME`, `secrets.SEED_AUTH_CLIENT_ID` to `vars.*` in all workflow files
    - _Requirements: 13.1_

  - [x] 11.2 Update `ACTIONS-REFERENCE.md` Type column for migrated values from "Secret" to "Variable"
    - _Requirements: 13.3_

  - [x] 11.3 Update `README-ACTIONS.md` references for migrated values
    - _Requirements: 13.4_

- [x] 12. Add validateConfig rules for enabled stacks
  - [x] 12.1 Add validation in `validateConfig()` for `gateway.apiType` when `gateway.enabled` is true
    - Verify `apiType` is `'REST'` or `'HTTP'`, throw descriptive error if not
    - _Requirements: 9.2_

  - [x] 12.2 Add validation in `validateConfig()` for CORS origins when `fileUpload.enabled` is true
    - Verify CORS origins available from top-level or section-level config
    - _Requirements: 9.3_

  - [x] 12.3 Add validation in `validateConfig()` for required fields on all enabled stacks
    - Throw descriptive error identifying missing field and which stack requires it
    - _Requirements: 9.1, 9.4_

- [x] 13. Synchronize cdk.context.json with config.ts
  - [x] 13.1 Ensure every `tryGetContext()` call in `loadConfig()` has a matching key in `cdk.context.json`
    - _Requirements: 8.1_

  - [x] 13.2 Remove orphaned non-framework keys from `cdk.context.json` that `loadConfig()` does not read
    - Preserve CDK framework keys (`availability-zones:*`, `@aws-cdk/*`, `acknowledged-issue-numbers`)
    - _Requirements: 8.2_

  - [x] 13.3 Fix any path mismatches between context keys and `tryGetContext()` read paths
    - E.g., if `domainName` is read from top-level but defined under `frontend`, move it
    - _Requirements: 8.3_

  - [x] 13.4 Ensure no sensitive values in `cdk.context.json` — use empty strings or placeholders
    - _Requirements: 8.4_

- [x] 14. Update retainDataOnDelete default
  - [x] 14.1 Set `retainDataOnDelete` to `false` in `cdk.context.json`
    - _Requirements: 16.1_

  - [x] 14.2 Remove hardcoded default for `retainDataOnDelete` from `config.ts` (already done in task 1.1, verify)
    - _Requirements: 16.2_

  - [x] 14.3 Remove `:-true` bash default for `CDK_RETAIN_DATA_ON_DELETE` from `load-env.sh` (already done in task 1.3, verify)
    - _Requirements: 16.3_

  - [x] 14.4 Update `ACTIONS-REFERENCE.md` default value for `CDK_RETAIN_DATA_ON_DELETE` from `true` to `false`
    - _Requirements: 16.4_

  - [x] 14.5 Update `README-ACTIONS.md` if `CDK_RETAIN_DATA_ON_DELETE` is referenced
    - _Requirements: 16.5_

- [x] 15. Update GitHub Actions workflow files for all removed config
  - [x] 15.1 Remove env entries for deleted fields from all `.github/workflows/*.yml` files
    - Remove: `ENV_INFERENCE_API_ENABLE_AUTHENTICATION`, `ENV_INFERENCE_API_OAUTH_CALLBACK_URL`, `CDK_ENABLE_AUTHENTICATION`, `CDK_FRONTEND_ENABLE_ROUTE53`, `CDK_INFERENCE_API_ENABLE_GPU`, `ENV_INFERENCE_API_UPLOAD_DIR`, `ENV_INFERENCE_API_OUTPUT_DIR`, `ENV_INFERENCE_API_GENERATED_IMAGES_DIR`, `ENV_INFERENCE_API_API_URL`, `ENV_INFERENCE_API_FRONTEND_URL`
    - _Requirements: 10.6, 12.6, 18.5_

  - [x] 15.2 Update `ACTIONS-REFERENCE.md` to remove entries for all deleted config variables
    - _Requirements: 10.6, 12.6, 18.6_

  - [x] 15.3 Update `README-ACTIONS.md` to remove references to deleted variables
    - _Requirements: 12.7_

- [x] 16. Checkpoint — full verification after all config changes
  - Run TypeScript compilation: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/infrastructure && npx tsc --noEmit"`
  - Run CDK synth with context defaults only: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/infrastructure && npx cdk synth --quiet"`
  - Run CDK tests: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/infrastructure && npm test"`
  - Run frontend tests: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/frontend/ai.client && npm test"`
  - Run backend tests: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/backend && python -m pytest tests/ -v"`
  - Grep for stale references: `docker compose exec dev grep -r "enableRds\|enableGpu\|databaseType\|ENABLE_AUTHENTICATION\|enableAuthentication\|inferenceApiUrl\|enableRoute53\|oauthCallbackUrl" --include="*.ts" --include="*.py" --include="*.sh" --include="*.yml" /workspace/bsu-org/agentcore-public-stack/ -l`
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Audit and clean up CloudFormation resource tagging
  - [x] 17.1 Remove hardcoded tag literals from `loadConfig()` in `config.ts`
    - Remove `Project: projectPrefix` and `ManagedBy: 'CDK'` from the `tags` object
    - Load tags entirely from `scope.node.tryGetContext('tags') || {}`
    - Update `applyStandardTags()` to inject `Project: config.projectPrefix` dynamically (since context can't interpolate) alongside context tags
    - _Requirements: 19.1, 19.3_

  - [x] 17.2 Clean up `tags` section in `cdk.context.json`
    - Remove `Environment: 'dev'` (doesn't reflect actual deployment)
    - Keep `ManagedBy: 'CDK'` as a context default
    - Remove `Project: 'AgentCore'` (will be injected dynamically from `projectPrefix`)
    - _Requirements: 19.2, 19.6_

  - [x] 17.3 Review `@aws-cdk/core:checksumAssetForResourceTags` context flag
    - Determine if it causes unexpected hash-based tags on resources
    - Set to `false` or remove if it does
    - _Requirements: 19.4_

  - [x] 17.4 Update CDK infrastructure tests for cleaned-up tag set
    - _Requirements: 19.5_

- [x] 18. Document configuration variable inventory
  - [x] 17.1 Create `docs/CONFIG_INVENTORY.md` with complete variable inventory
    - List every `.env.example` variable with consuming Python module path
    - List every `cdk.context.json` key with consuming `config.ts` field
    - List every frontend environment field with consuming Angular service
    - Flag any variable defined but not consumed as "unused"
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 17.2 Final update to `ACTIONS-REFERENCE.md` for consolidated CORS and all remaining changes
    - Ensure all deleted variables are removed, renamed/consolidated variables are reflected
    - _Requirements: 12.6_

  - [x] 17.3 Final update to `README-ACTIONS.md` for any remaining references
    - _Requirements: 12.7_

- [x] 19. Final checkpoint — end-to-end verification
  - Run TypeScript compilation: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/infrastructure && npx tsc --noEmit"`
  - Run CDK synth: `docker compose exec dev bash -c "cd /workspace/bsu-org/agentcore-public-stack/infrastructure && npx cdk synth --quiet"`
  - Run all test suites (CDK, frontend, backend)
  - Final grep for all removed field names to confirm zero stale references
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All runtime commands must use `docker compose exec dev <command>` — never run directly on the host
- No new permanent test files are created; existing tests are updated to remove references to deleted fields
- Tasks are ordered so that structural changes (default hierarchy, interface removals) happen first, reducing merge conflicts
- Req 15 (remove inferenceApiUrl) depends on Req 14 (remove auth toggle) being done first — task ordering reflects this
- Req 8 (sync context) and Req 12 (documentation) are near the end since they inventory the final state
- Checkpoints at tasks 5, 16, and 18 ensure incremental verification
- Each task references specific requirement clauses for traceability

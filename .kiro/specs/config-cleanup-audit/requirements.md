# Requirements Document

## Introduction

Audit and clean up redundant, unused, or unnecessary configuration variables across the entire AgentCore Public Stack codebase. Configuration is spread across backend environment variables (.env), frontend environment files, CDK infrastructure config (config.ts, cdk.context.json), and Docker/script files. Over time, dead config has accumulated — RDS fields that are hardcoded to disabled, CORS origins duplicated across four config sections, inference API fields that exist in CDK config but are never passed to containers, and GPU flags that are defined but never consumed by any stack. This feature removes the dead weight, consolidates duplicates, and ensures every remaining config variable is actually used and documented.

## Glossary

- **CDK_Config**: The infrastructure configuration system in `infrastructure/lib/config.ts` that loads values from environment variables and CDK context (`cdk.context.json`)
- **Env_File**: The backend `.env` file (template at `backend/src/.env.example`) containing runtime environment variables for the App API and Inference API
- **Frontend_Env**: The Angular environment files at `frontend/ai.client/src/environments/` that provide compile-time and fallback runtime configuration
- **Context_File**: The `infrastructure/cdk.context.json` file containing CDK context values used as defaults for infrastructure configuration
- **Audit_Report**: A structured inventory of every configuration variable with its usage status (used, unused, redundant, or deprecated)
- **CORS_Config**: Cross-Origin Resource Sharing origin lists, currently duplicated across `inferenceApi`, `fileUpload`, `assistants`, and `ragIngestion` config sections

## Requirements

### Requirement 1: Identify and Remove Unused RDS Configuration

**User Story:** As a developer, I want dead RDS configuration removed from the codebase, so that the config interfaces are not cluttered with fields that are hardcoded to disabled and never consumed by any stack.

#### Acceptance Criteria

1. WHEN the CDK_Config is loaded, THE CDK_Config SHALL NOT contain the `enableRds`, `rdsInstanceClass`, `rdsEngine`, or `rdsDatabaseName` fields in the `AppApiConfig` interface
2. WHEN the Context_File is loaded, THE Context_File SHALL NOT contain `enableRds`, `rdsInstanceClass`, `rdsEngine`, or `rdsDatabaseName` keys in the `appApi` section
3. IF any infrastructure stack references removed RDS fields, THEN THE CDK_Config SHALL produce a compilation error at build time

### Requirement 2: Identify and Remove Unused GPU Configuration

**User Story:** As a developer, I want the unused `enableGpu` flag removed, so that the inference API config does not advertise a capability that no infrastructure stack actually provisions.

#### Acceptance Criteria

1. WHEN the CDK_Config is loaded, THE CDK_Config SHALL NOT contain the `enableGpu` field in the `InferenceApiConfig` interface
2. WHEN the Context_File is loaded, THE Context_File SHALL NOT contain the `enableGpu` key in the `inferenceApi` section
3. IF any infrastructure stack references the removed `enableGpu` field, THEN THE CDK_Config SHALL produce a compilation error at build time

### Requirement 3: Consolidate Duplicated CORS Origins Configuration

**User Story:** As a developer, I want CORS origins defined in one place instead of four separate config sections, so that I do not have to update the same value in `inferenceApi`, `fileUpload`, `assistants`, and `ragIngestion` every time a domain changes.

#### Acceptance Criteria

1. THE CDK_Config SHALL define a single top-level `corsOrigins` field in the `AppConfig` interface for shared CORS origin values
2. WHEN a stack requires CORS origins, THE CDK_Config SHALL provide the top-level `corsOrigins` value as the default
3. WHERE a stack requires stack-specific CORS origins that differ from the default, THE CDK_Config SHALL allow an optional per-section `corsOrigins` override
4. WHEN the Context_File is updated, THE Context_File SHALL contain a single top-level `corsOrigins` value instead of duplicated values across `fileUpload`, `assistants`, and `ragIngestion` sections
5. THE CDK_Config SHALL maintain backward compatibility by falling back to per-section `corsOrigins` values if the top-level value is not set

### Requirement 4: Remove Inference API Directory Config from CDK

**User Story:** As a developer, I want the `uploadDir`, `outputDir`, and `generatedImagesDir` fields removed from the CDK infrastructure config, so that container-internal directory paths are not managed as infrastructure-level configuration when they are never injected into deployed containers and serve no purpose in the CDK config.

#### Acceptance Criteria

1. WHEN the CDK_Config is loaded, THE CDK_Config SHALL NOT contain `uploadDir`, `outputDir`, or `generatedImagesDir` fields in the `InferenceApiConfig` interface
2. WHEN the Context_File is loaded, THE Context_File SHALL NOT contain `uploadDir`, `outputDir`, or `generatedImagesDir` keys in the `inferenceApi` section
3. THE CDK infrastructure tests SHALL NOT reference `uploadDir`, `outputDir`, or `generatedImagesDir` in test context setup
4. THE Env_File SHALL continue to define `UPLOAD_DIR`, `OUTPUT_DIR`, and `GENERATED_IMAGES_DIR` as local-development-only configuration, with comments clarifying that in deployed cloud environments these values are unused because the Dockerfiles create the directories at build time and the Python code falls back to hardcoded defaults

### Requirement 5: Remove Hardcoded databaseType Configuration

**User Story:** As a developer, I want the `databaseType` field removed from `AppApiConfig`, so that a config field hardcoded to `'none'` in the loader does not mislead developers into thinking it is configurable.

#### Acceptance Criteria

1. WHEN the CDK_Config is loaded, THE CDK_Config SHALL NOT contain the `databaseType` field in the `AppApiConfig` interface
2. WHEN the Context_File is loaded, THE Context_File SHALL NOT contain a `databaseType` key in the `appApi` section
3. IF any infrastructure stack references the removed `databaseType` field, THEN THE CDK_Config SHALL produce a compilation error at build time

### Requirement 6: Synchronize .env.example with Actual Usage

**User Story:** As a developer, I want the `.env.example` file to accurately reflect which environment variables are actually consumed by the codebase, so that new developers do not waste time configuring variables that nothing reads.

#### Acceptance Criteria

1. THE Env_File SHALL document only environment variables that are referenced by at least one Python module via `os.environ` or `os.getenv`
2. WHEN an environment variable is loaded via `os.getenv` or `os.environ`, THE loaded value SHALL be verified to have meaningful downstream usage (e.g., passed to a function, used in a condition, or assigned to a consumed field) — if the value is loaded but never meaningfully used, all remnants of it (the `os.getenv` call, any associated variable, and the `.env.example` entry) SHALL be removed
3. WHEN an environment variable is removed from all Python source files, THE Env_File SHALL remove the corresponding entry from `.env.example`
4. WHEN a new environment variable is added to a Python source file, THE Env_File SHALL include a corresponding documented entry in `.env.example`
5. THE Env_File SHALL group related variables under clearly labeled section headers

### Requirement 7: Remove Dead Frontend Environment Imports

**User Story:** As a developer, I want dead imports of the `environment` object removed from Angular source files that do not actually use it, so that the codebase does not give the false impression that environment files are consumed outside of `ConfigService`.

#### Acceptance Criteria

1. IF an Angular source file imports from `environments/environment` but does not reference the imported symbol in its executable code, THEN the import SHALL be removed
2. THE `ConfigService` SHALL remain the only Angular service that imports from `environments/environment`

### Requirement 8: Synchronize cdk.context.json with config.ts

**User Story:** As a developer, I want `cdk.context.json` to be a complete and accurate mirror of the context fallbacks defined in `loadConfig()`, so that every context-backed field has a sensible default and no stale or orphaned keys remain.

#### Acceptance Criteria

1. FOR every field in `loadConfig()` that reads from `scope.node.tryGetContext()`, THE Context_File SHALL contain a corresponding key with a sensible non-sensitive default value
2. THE Context_File SHALL NOT contain keys that are not read by `loadConfig()` or by CDK framework internals (e.g., `availability-zones:*`, `@aws-cdk/*`, `acknowledged-issue-numbers`)
3. WHERE `loadConfig()` reads a context key from a different path than where it exists in the Context_File (e.g., `domainName` read from top-level but defined under `frontend`), THE Context_File SHALL move the key to match the path that `loadConfig()` actually reads
4. THE Context_File SHALL NOT contain sensitive values (API keys, secrets, account IDs) — these SHALL be empty strings or placeholder values
5. WHEN other requirements in this spec remove fields from config interfaces (RDS, GPU, directory paths, databaseType), THE Context_File SHALL also remove the corresponding context keys

### Requirement 9: Validate Configuration Completeness at Startup

**User Story:** As a developer, I want the CDK config validation to catch missing or contradictory configuration at synth time, so that deployment failures caused by incomplete config are caught early.

#### Acceptance Criteria

1. WHEN `validateConfig()` runs, THE CDK_Config SHALL verify that all enabled stacks have their required configuration fields populated
2. WHEN `gateway.enabled` is true, THE CDK_Config SHALL verify that `gateway.apiType` is either `'REST'` or `'HTTP'`
3. WHEN `fileUpload.enabled` is true, THE CDK_Config SHALL verify that CORS origins are available (either from top-level or section-level config)
4. IF a required field is missing for an enabled stack, THEN THE CDK_Config SHALL throw a descriptive error identifying the missing field and which stack requires it

### Requirement 10: Remove enableRoute53 Flag and Derive Route53 from domainName

**User Story:** As a developer, I want the `enableRoute53` flag removed from the frontend config, so that Route53 DNS record creation is automatically derived from whether `domainName` is set — matching the same pattern the infrastructure stack uses for the ALB Route53 record.

#### Acceptance Criteria

1. THE CDK_Config SHALL remove the `enableRoute53` field from the `FrontendConfig` interface
2. THE Context_File SHALL remove the `enableRoute53` key from the `frontend` section
3. THE frontend stack SHALL create a Route53 A record when `config.domainName` is set (instead of checking `config.frontend.enableRoute53 && config.domainName`)
4. THE `loadConfig()` function SHALL NOT load `CDK_FRONTEND_ENABLE_ROUTE53` from environment or context
5. THE CDK infrastructure tests SHALL be updated to remove `enableRoute53` from test context setup
6. THE GitHub Actions reference docs SHALL remove the `CDK_FRONTEND_ENABLE_ROUTE53` variable entry

### Requirement 11: Remove Stale Entra ID Configuration Remnants

**User Story:** As a developer, I want the legacy Entra-specific configuration variables removed from CDK tests and GitHub Actions documentation, so that the codebase reflects the current generic OIDC provider model and does not mislead developers into configuring Entra-specific CDK variables that nothing reads.

#### Acceptance Criteria

1. THE CDK infrastructure tests SHALL NOT set `entraClientId`, `entraTenantId`, or `entraRedirectUri` in test context setup, since `loadConfig()` does not read these values
2. THE GitHub Actions reference at `.github/ACTIONS-REFERENCE.md` SHALL remove the `CDK_ENTRA_CLIENT_ID`, `CDK_ENTRA_TENANT_ID`, and `CDK_APP_API_ENTRA_REDIRECT_URI` entries
3. THE GitHub Actions quick-start guide at `.github/README-ACTIONS.md` SHALL replace the Entra-specific authentication guidance with a reference to the generic OIDC provider seeding workflow (`SEED_AUTH_*` variables)
4. THE Context_File SHALL NOT contain `entraClientId` or `entraTenantId` keys if they are present

### Requirement 12: Document Configuration Variable Inventory

**User Story:** As a developer, I want a single reference document listing every configuration variable, where it is defined, and where it is consumed, so that future audits are straightforward.

#### Acceptance Criteria

1. THE Audit_Report SHALL list every environment variable from `.env.example` with its consuming Python module path
2. THE Audit_Report SHALL list every CDK context key from `cdk.context.json` with its consuming config.ts field
3. THE Audit_Report SHALL list every frontend environment field with its consuming Angular service
4. THE Audit_Report SHALL flag any variable that is defined but not consumed as "unused"
5. THE Audit_Report SHALL be stored in `docs/CONFIG_INVENTORY.md`
6. THE GitHub Actions configuration reference at `.github/ACTIONS-REFERENCE.md` SHALL be updated to remove entries for any configuration variables deleted by this spec (e.g., `CDK_INFERENCE_API_ENABLE_GPU`, `ENV_INFERENCE_API_UPLOAD_DIR`, `ENV_INFERENCE_API_OUTPUT_DIR`, `ENV_INFERENCE_API_GENERATED_IMAGES_DIR`) and to reflect any renamed or consolidated variables (e.g., CORS origins consolidation)
7. THE GitHub Actions quick-start guide at `.github/README-ACTIONS.md` SHALL be updated if any removed or renamed variables are referenced in its examples or next-steps section

### Requirement 13: Migrate Non-Sensitive GitHub Secrets to Variables

**User Story:** As a developer, I want non-sensitive configuration values moved from GitHub Secrets to GitHub Variables, so that secrets are reserved for genuinely sensitive data and non-sensitive values are easier to inspect and manage.

#### Acceptance Criteria

1. THE following values SHALL be changed from `secrets.*` to `vars.*` in all workflow files where they appear:
   - `CDK_AWS_ACCOUNT` — AWS account IDs are not credentials and appear in every ARN
   - `CDK_FRONTEND_CERTIFICATE_ARN` — a resource ARN, not a credential
   - `CDK_FRONTEND_BUCKET_NAME` — a bucket name, not a credential
   - `SEED_AUTH_CLIENT_ID` — OAuth client IDs are public identifiers (the secret is `CLIENT_SECRET`)
2. THE following values SHALL remain as `secrets.*` because they are genuinely sensitive:
   - `AWS_ACCESS_KEY_ID` — AWS credential
   - `AWS_SECRET_ACCESS_KEY` — AWS credential
   - `AWS_ROLE_ARN` — IAM role ARN (allows assuming a role)
   - `ENV_INFERENCE_API_TAVILY_API_KEY` — third-party API key
   - `ENV_INFERENCE_API_NOVA_ACT_API_KEY` — third-party API key
   - `SEED_AUTH_CLIENT_SECRET` — OAuth client secret
3. THE `.github/ACTIONS-REFERENCE.md` SHALL update the Type column for each migrated value from "Secret" to "Variable"
4. THE `.github/README-ACTIONS.md` SHALL update any references to migrated values to reflect their new type

### Requirement 14: Remove Authentication Enable/Disable Configuration

**User Story:** As a developer, I want the `ENABLE_AUTHENTICATION` toggle and all its variants removed from the configuration surface, so that authentication is always enabled and there is no risk of accidentally deploying with auth disabled. The application requires authentication to function correctly in any deployed environment.

#### Acceptance Criteria

1. THE backend `dependencies.py` SHALL remove the `ENABLE_AUTHENTICATION` environment variable check and the `_check_auth_bypass()` function — authentication SHALL always be enforced
2. THE backend `dependencies.py` SHALL remove the `_create_anonymous_dev_user()` function since auth bypass is no longer supported
3. THE backend `jwt_validator.py` SHALL remove the `ENABLE_AUTHENTICATION` environment variable check
4. THE backend `inference_api/main.py` SHALL remove the `ENABLE_AUTHENTICATION` log line since the value is no longer configurable
5. THE Env_File SHALL remove the `ENABLE_AUTHENTICATION` entry from `.env.example`
6. THE frontend `ConfigService` SHALL remove `enableAuthentication` from the `RuntimeConfig` interface and all computed signals, defaulting all auth checks to `true`
7. THE frontend `environment.ts` and `environment.production.ts` SHALL remove the `enableAuthentication` field
8. THE frontend components that check `config.enableAuthentication()` (auth guard, admin guard, auth interceptor, auth service, user service, chat-http service) SHALL be updated to remove the conditional bypass paths
9. THE CDK config SHALL remove `CDK_ENABLE_AUTHENTICATION` from all GitHub Actions workflow files, `load-env.sh`, and `ACTIONS-REFERENCE.md`
10. THE CDK config SHALL remove `ENV_INFERENCE_API_ENABLE_AUTHENTICATION` from all GitHub Actions workflow files, `config.ts` `InferenceApiConfig` interface, and `ACTIONS-REFERENCE.md`
11. THE frontend build script (`scripts/stack-frontend/build.sh`) SHALL remove the `ENABLE_AUTHENTICATION` sed replacement logic
12. THE backend auth README at `backend/src/apis/shared/auth/README.md` SHALL be updated to remove documentation about the `ENABLE_AUTHENTICATION` toggle and the stale Entra-specific environment variable references

### Requirement 15: Remove Static inferenceApiUrl Configuration

**User Story:** As a developer, I want the static `inferenceApiUrl` configuration removed from the frontend and CDK config, because AgentCore Runtimes are provisioned dynamically per auth provider and there is no default or static inference API endpoint. The frontend already resolves the runtime endpoint dynamically via the App API based on the authenticated user's provider.

#### Acceptance Criteria

1. THE frontend `RuntimeConfig` interface in `ConfigService` SHALL remove the `inferenceApiUrl` field
2. THE frontend `ConfigService` SHALL remove the `inferenceApiUrl` computed signal and the `encodeUrlPath` helper method
3. THE frontend `environment.ts` SHALL remove the `inferenceApiUrl` field (the `http://localhost:8001` fallback is meaningless)
4. THE frontend `environment.production.ts` SHALL remove the `inferenceApiUrl` field
5. THE frontend `config.service.spec.ts` SHALL be updated to remove all `inferenceApiUrl` test cases
6. THE frontend `chat-http.service.ts` SHALL remove the static `inferenceApiUrl` fallback branch (the `!config.enableAuthentication()` path is already removed by Requirement 14; the only remaining path is the dynamic `getRuntimeEndpointUrl()` via `authApiService`)
7. THE frontend `preview-chat.service.ts` SHALL be updated to resolve the runtime endpoint dynamically via `authApiService.getRuntimeEndpoint()` instead of using the static `config.inferenceApiUrl()`
8. THE CDK frontend stack SHALL stop generating `inferenceApiUrl` in the runtime `config.json` if it currently does so
9. THE CDK `InferenceApiConfig` interface SHALL remove any fields related to a static inference API URL (e.g., `apiUrl`, `frontendUrl`) that are not consumed by any deployed resource
10. THE `.env.example` SHALL remove any inference API URL entries that are no longer consumed
11. THE `ACTIONS-REFERENCE.md` SHALL remove `ENV_INFERENCE_API_API_URL` and `ENV_INFERENCE_API_FRONTEND_URL` entries if they are no longer consumed by any stack

### Requirement 16: Change retainDataOnDelete Default to False

**User Story:** As a developer, I want `retainDataOnDelete` to default to `false`, so that development and test stacks clean up their resources on deletion by default instead of retaining orphaned DynamoDB tables and S3 buckets that accumulate cost.

#### Acceptance Criteria

1. THE Context_File SHALL set the `retainDataOnDelete` value to `false` — `cdk.context.json` is the single source of truth for default values per the configuration hierarchy (`Environment Variables > CDK Context > Defaults`)
2. THE `loadConfig()` function in `config.ts` SHALL NOT define a hardcoded default for `retainDataOnDelete` — it SHALL read from the environment variable and fall back to CDK context, which provides the default via `cdk.context.json`
3. THE `load-env.sh` script SHALL NOT define a hardcoded default for `CDK_RETAIN_DATA_ON_DELETE` — it SHALL read from the environment variable and fall back to the context file value (removing the `:-true` bash default)
4. THE `ACTIONS-REFERENCE.md` SHALL update the default value for `CDK_RETAIN_DATA_ON_DELETE` from `true` to `false`
5. THE `README-ACTIONS.md` SHALL note the default change if `CDK_RETAIN_DATA_ON_DELETE` is referenced in its guidance

### Requirement 17: Enforce Configuration Default Hierarchy — Defaults in CDK Context Only

**User Story:** As a developer, I want all configuration default values to live exclusively in `cdk.context.json`, so that the configuration hierarchy (`Environment Variables > CDK Context > Defaults`) is enforced consistently and there is exactly one place to look up or change any default.

#### Acceptance Criteria

1. THE `loadConfig()` function in `config.ts` SHALL NOT contain hardcoded fallback values for any configuration field — each field SHALL read from its environment variable first, then fall back to `scope.node.tryGetContext()`, with no trailing `|| <literal>` or second argument to `parseBooleanEnv()` / `parseIntEnv()` that acts as a default
2. THE following hardcoded defaults in `loadConfig()` SHALL be removed and their values moved to corresponding keys in the Context_File:
   - `production: parseBooleanEnv(..., true)` → context key `production` set to `true`
   - `retainDataOnDelete: parseBooleanEnv(..., true)` → context key `retainDataOnDelete` set to `false` (per Requirement 16)
   - `fileUpload.enabled: ... ?? true` → context key `fileUpload.enabled` set to `true`
   - `fileUpload.maxFileSizeBytes: ... || 4 * 1024 * 1024` → context key `fileUpload.maxFileSizeBytes` set to `4194304`
   - `fileUpload.maxFilesPerMessage: ... || 5` → context key `fileUpload.maxFilesPerMessage` set to `5`
   - `fileUpload.userQuotaBytes: ... || 1024 * 1024 * 1024` → context key `fileUpload.userQuotaBytes` set to `1073741824`
   - `fileUpload.retentionDays: ... || 365` → context key `fileUpload.retentionDays` set to `365`
   - `assistants.enabled: ... ?? true` → context key `assistants.enabled` set to `true`
   - `ragIngestion.enabled: ... ?? true` → context key `ragIngestion.enabled` set to `true`
   - `ragIngestion.lambdaMemorySize: ... || 10240` → context key `ragIngestion.lambdaMemorySize` set to `10240`
   - `ragIngestion.lambdaTimeout: ... || 900` → context key `ragIngestion.lambdaTimeout` set to `900`
   - `ragIngestion.embeddingModel: ... || 'amazon.titan-embed-text-v2'` → context key `ragIngestion.embeddingModel` set to `"amazon.titan-embed-text-v2"`
   - `ragIngestion.vectorDimension: ... || 1024` → context key `ragIngestion.vectorDimension` set to `1024`
   - `ragIngestion.vectorDistanceMetric: ... || 'cosine'` → context key `ragIngestion.vectorDistanceMetric` set to `"cosine"`
3. THE `load-env.sh` script SHALL NOT contain hardcoded bash defaults (e.g., `:-true`, `:-10`) for any CDK configuration variable — it SHALL read from the environment variable first, then fall back to the context file via `get_json_value`, matching the hierarchy
4. THE following hardcoded defaults in `load-env.sh` SHALL be removed:
   - `CDK_FILE_UPLOAD_CORS_ORIGINS` `:-http://localhost:4200` → fall back to context file value
   - `CDK_FILE_UPLOAD_MAX_SIZE_MB` `:-10` → fall back to context file value
5. EXCEPTION: Empty-string fallbacks (`|| ''`) in `config.ts` for fields like `imageTag`, `oauthCallbackUrl`, and `ragIngestion.corsOrigins` are acceptable — these represent "not set" sentinels rather than meaningful defaults and SHALL be retained as-is
6. THE Context_File SHALL contain a complete set of default values for every field enumerated in criterion 2, ensuring that a fresh clone with no environment variables set can synthesize successfully using only context defaults

### Requirement 18: Remove Dead oauthCallbackUrl from Inference API Config

**User Story:** As a developer, I want the `oauthCallbackUrl` field removed from the `InferenceApiConfig` interface and all its upstream plumbing, because the OAuth callback URL is already derived from `domainName` or the ALB URL in `InfrastructureStack`, written to SSM, and injected into containers by the runtime provisioner Lambda — making the CDK config field dead code that nothing consumes.

#### Acceptance Criteria

1. THE `InferenceApiConfig` interface in `config.ts` SHALL remove the `oauthCallbackUrl` field
2. THE `loadConfig()` function SHALL remove the `oauthCallbackUrl` line that reads from `ENV_INFERENCE_API_OAUTH_CALLBACK_URL`
3. THE `load-env.sh` script SHALL remove the `ENV_INFERENCE_API_OAUTH_CALLBACK_URL` export and its context parameter block
4. THE Context_File SHALL remove the `oauthCallbackUrl` key from the `inferenceApi` section if present
5. THE GitHub Actions workflow `inference-api.yml` SHALL remove `ENV_INFERENCE_API_OAUTH_CALLBACK_URL` from its `env:` sections
6. THE `ACTIONS-REFERENCE.md` SHALL remove the `ENV_INFERENCE_API_OAUTH_CALLBACK_URL` entry
7. THE Requirement 17 empty-string exception list SHALL be updated to remove `oauthCallbackUrl` since the field no longer exists

### Requirement 19: Audit and Clean Up CloudFormation Resource Tagging

**User Story:** As a developer, I want resource tags to be predictable, minimal, and fully driven by `cdk.context.json`, so that I do not see unexpected tags on deployed resources and every tag has a clear origin.

#### Acceptance Criteria

1. THE `tags` object in `loadConfig()` SHALL be loaded entirely from `scope.node.tryGetContext('tags')` — the hardcoded `Project: projectPrefix` and `ManagedBy: 'CDK'` literals SHALL be removed from `config.ts` and moved to the `tags` section in `cdk.context.json` as the defaults
2. THE Context_File `tags` section SHALL contain only intentional, documented tags — remove any stale or unexpected tags (e.g., `Environment: 'dev'` should not be hardcoded if it does not reflect the actual deployment environment)
3. THE `applyStandardTags()` function SHALL apply only the tags from `config.tags` — no additional tags SHALL be injected by application code
4. THE `@aws-cdk/core:checksumAssetForResourceTags` context flag SHALL be reviewed — if it causes CDK to inject unexpected hash-based tags on resources, it SHALL be set to `false` or removed
5. THE CDK infrastructure tests SHALL be updated to reflect the cleaned-up tag set
6. THE `tags` section in `cdk.context.json` SHALL use `projectPrefix` value interpolation or a clear placeholder so that the `Project` tag matches the actual project prefix at deploy time, not a hardcoded string like `"AgentCore"`

# Requirements: Versioning Strategy

## Requirement 1: Single Source of Truth

### User Story
As a developer, I want a single VERSION file at the repo root that defines the monorepo's version, so I don't have to update multiple files manually or wonder which one is authoritative.

### Acceptance Criteria
- [ ] A `VERSION` file exists at the repository root containing a single line with the version string
- [ ] The version string follows SemVer 2.0 format: `MAJOR.MINOR.PATCH[-PRERELEASE]`
- [ ] The VERSION file validates against regex: `^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$`
- [ ] The initial version is set to `1.0.0-beta.1`
- [ ] The file contains no leading `v` prefix (the `v` is added only in git tags)
- [ ] The file contains exactly one line with no trailing whitespace beyond a single newline

---

## Requirement 2: Package Manifest Sync

### User Story
As a developer, I want a script that propagates the VERSION file value into all package manifests, so they stay in sync without manual editing.

### Acceptance Criteria
- [ ] A script exists at `scripts/common/sync-version.sh` that reads the VERSION file
- [ ] Running the script without flags updates the `version` field in `backend/pyproject.toml`
- [ ] Running the script without flags updates the `version` field in `frontend/ai.client/package.json`
- [ ] Running the script without flags updates the `version` field in `infrastructure/package.json`
- [ ] Running the script with `--check` exits non-zero if any manifest version doesn't match VERSION
- [ ] Running the script with `--check` does not modify any files
- [ ] The script exits with a clear error message if the VERSION file is missing or malformed
- [ ] The script uses `set -euo pipefail` for error handling

---

## Requirement 3: Backend Health Endpoint Versioning

### User Story
As an operator, I want the health endpoints to return the running version, so I can verify which version is deployed without checking ECR or SSM.

### Acceptance Criteria
- [ ] App API `/health` endpoint response includes a `"version"` field read from the `APP_VERSION` environment variable
- [ ] Inference API `/ping` endpoint response includes a `"version"` field read from the `APP_VERSION` environment variable
- [ ] Both endpoints fall back to `"version": "unknown"` when `APP_VERSION` is not set (local dev)
- [ ] The FastAPI `app` object `version` parameter in both `main.py` files reads from `APP_VERSION` env var instead of a hardcoded string
- [ ] The hardcoded `"2.0.0"` version string is removed from all backend files

---

## Requirement 4: Docker Build-Time Version Injection

### User Story
As a CI pipeline, I want to bake the version into Docker images at build time, so containers know their version at runtime without external lookups.

### Acceptance Criteria
- [ ] `Dockerfile.app-api` accepts an `APP_VERSION` build arg and sets `ENV APP_VERSION=${APP_VERSION}`
- [ ] `Dockerfile.inference-api` accepts an `APP_VERSION` build arg and sets `ENV APP_VERSION=${APP_VERSION}`
- [ ] `Dockerfile.rag-ingestion` accepts an `APP_VERSION` build arg and sets `ENV APP_VERSION=${APP_VERSION}`
- [ ] Build scripts (`scripts/stack-app-api/build.sh`, `scripts/stack-inference-api/build.sh`) pass `--build-arg APP_VERSION` to `docker build`
- [ ] The `APP_VERSION` value defaults to `"unknown"` if the build arg is not provided

---

## Requirement 5: Docker Image Dual-Tagging

### User Story
As an operator, I want Docker images tagged with both a semver tag and a git SHA tag, so I can identify releases by version and trace them back to specific commits.

### Acceptance Criteria
- [ ] ECR images for App API are tagged with both the semver version (e.g. `1.0.0-beta.1`) and the short git SHA (e.g. `abc1234`)
- [ ] ECR images for Inference API are tagged with both the semver version and the short git SHA
- [ ] ECR images for RAG Ingestion are tagged with both the semver version and the short git SHA
- [ ] `push-to-ecr.sh` scripts push both tags for each image
- [ ] SSM parameters (`/{prefix}/app-api/image-tag`, `/{prefix}/inference-api/image-tag`) store the semver tag instead of the SHA tag
- [ ] The `latest` and `deployed-<SHA>` tags continue to be applied post-deploy as before

---

## Requirement 6: CI/CD Workflow Version Integration

### User Story
As a CI pipeline, I want workflows to read the VERSION file and pass it through the build/push/deploy pipeline, so the version flows automatically from source to production.

### Acceptance Criteria
- [ ] The `build-docker` job in `app-api.yml` reads the VERSION file and outputs `APP_VERSION`
- [ ] The `build-docker` job in `inference-api.yml` reads the VERSION file and outputs `APP_VERSION`
- [ ] The `build-docker` job in `rag-ingestion.yml` reads the VERSION file and outputs `APP_VERSION`
- [ ] Docker build steps pass `--build-arg APP_VERSION=$APP_VERSION`
- [ ] The `frontend.yml` workflow reads the VERSION file and passes it as CDK context (`--context appVersion=...`)
- [ ] All workflows that run `cdk deploy` pass the version via `CDK_APP_VERSION` env var or `--context appVersion`

---

## Requirement 7: Frontend Version Display

### User Story
As a user, I want to see the application version in the frontend UI, so I can report which version I'm using when filing issues.

### Acceptance Criteria
- [ ] The `RuntimeConfig` interface in `ConfigService` includes a `version` field of type `string`
- [ ] `ConfigService` exposes a `version` computed signal that returns the version from config
- [ ] `environment.ts` (local dev) includes `version: 'dev'` as a fallback value
- [ ] `environment.production.ts` includes `version: ''` as a fallback placeholder
- [ ] CDK `FrontendStack` includes `version` in the generated `config.json` object, read from config
- [ ] `config.ts` loads the app version from `CDK_APP_VERSION` env var or CDK context (`appVersion`)
- [ ] The version is displayed somewhere visible in the frontend UI (sidebar footer, header tooltip, or settings page)

---

## Requirement 8: AWS Resource Tagging

### User Story
As an operator, I want all AWS resources tagged with the deployed version, so I can filter resources by version in the AWS console and use it for cost allocation.

### Acceptance Criteria
- [ ] `AppConfig` interface in `config.ts` includes an `appVersion` field
- [ ] `loadConfig()` in `config.ts` loads `appVersion` from `CDK_APP_VERSION` env var or CDK context
- [ ] `applyStandardTags()` adds a `Version` tag with the value from `config.appVersion` to every stack
- [ ] The `Version` tag is applied to all resources across all 7 stacks (Infrastructure, App API, Inference API, Frontend, Gateway, RAG Ingestion)
- [ ] `scripts/common/load-env.sh` exports `CDK_APP_VERSION` by reading the VERSION file
- [ ] All `synth.sh` and `deploy.sh` scripts pass `--context appVersion=...` to CDK commands

---

## Requirement 9: PR Version Gate

### User Story
As a team lead, I want PRs to `main` blocked if the VERSION file hasn't been bumped or manifests are out of sync, so we never merge unversioned changes to production.

### Acceptance Criteria
- [ ] A workflow exists at `.github/workflows/version-check.yml` that triggers on all PRs to `main`
- [ ] The workflow has no path filters — it runs on every PR regardless of files changed
- [ ] The workflow fails if the VERSION file content is identical to `main` branch (version not bumped)
- [ ] The workflow fails if `sync-version.sh --check` exits non-zero (manifests out of sync)
- [ ] Both checks run regardless of the other's result (developer sees all failures at once)
- [ ] The workflow requires no AWS credentials, Docker, or dependency installation (bash + git only)
- [ ] The workflow job name is suitable for use as a required status check in branch protection settings

---

## Requirement 10: Git Tagging

### User Story
As a developer, I want git tags created automatically on successful deploys to `main`, so I can reference specific releases and roll back if needed.

### Acceptance Criteria
- [ ] After successful deploy on `main`, CI creates an annotated git tag `v<VERSION>` (e.g. `v1.0.0-beta.1`)
- [ ] The tagging step is idempotent — it skips if the tag already exists
- [ ] Tags are not created on `develop` or PR branches
- [ ] The CI workflow has `contents: write` permission to push tags
- [ ] The tag message includes the version string (e.g. `"Release 1.0.0-beta.1"`)

---

## Requirement 11: AI Assistant Versioning Guides

### User Story
As a developer using AI coding assistants, I want the assistants to already know how to bump the version, so I don't have to explain the process each time.

### Acceptance Criteria
- [ ] A Claude Code skill exists at `.claude/skills/versioning/SKILL.md` with concise version bump instructions
- [ ] A Cursor rule exists at `.cursor/rules/versioning.mdc` with `alwaysApply: true` and concise version bump instructions
- [ ] A Kiro steering file exists at `.kiro/steering/versioning.md` (always included, no frontmatter) with concise version bump instructions
- [ ] All three files contain the same core information: VERSION file location, SemVer format, sync script command, PR gate behavior, and that CI handles the rest
- [ ] Each file is under ~20 lines of content (quick reference, not a tutorial)

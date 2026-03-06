# Implementation Plan: Versioning Strategy

## Overview

Implement a unified versioning strategy for the monorepo using a single `VERSION` file as the source of truth. The version flows through a sync script, Docker builds, CI/CD workflows, health endpoints, frontend config, AWS resource tags, a PR gate, git tags, and AI assistant guides. Tasks are ordered so each step builds on the previous — starting with the VERSION file and sync script, then wiring version into backend, Docker, infrastructure, frontend, CI/CD, and finally the PR gate and AI guides.

## Tasks

- [x] 1. Create VERSION file and sync script
  - [x] 1.1 Create the VERSION file at the repo root
    - Create `VERSION` with content `1.0.0-beta.1` (single line, no `v` prefix, no trailing whitespace)
    - Validate it matches SemVer regex: `^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 1.2 Create `scripts/common/sync-version.sh`
    - Read VERSION file, validate format (exit with error if missing or malformed)
    - Update `version` field in `backend/pyproject.toml` via sed
    - Update `version` field in `frontend/ai.client/package.json` via sed or jq
    - Update `version` field in `infrastructure/package.json` via sed or jq
    - Implement `--check` mode that exits non-zero on drift without modifying files
    - Use `set -euo pipefail` for error handling
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 1.3 Write tests for sync-version.sh
    - Test sync mode updates all three manifests correctly
    - Test `--check` mode detects drift and exits non-zero
    - Test `--check` mode does not modify files
    - Test error handling for missing or malformed VERSION file
    - _Requirements: 2.5, 2.6, 2.7_

- [x] 2. Update backend health endpoints to expose version
  - [x] 2.1 Update App API health endpoint and FastAPI app version
    - Modify `backend/src/apis/app_api/health/health.py` to read `APP_VERSION` env var
    - Include `"version"` field in `/health` response, fallback to `"unknown"`
    - Update `backend/src/apis/app_api/main.py` FastAPI `version` parameter to read from `APP_VERSION` env var
    - Remove hardcoded `"2.0.0"` version string
    - _Requirements: 3.1, 3.3, 3.4, 3.5_

  - [x] 2.2 Update Inference API ping endpoint and FastAPI app version
    - Modify `backend/src/apis/inference_api/chat/routes.py` to include `"version"` field in `/ping` response
    - Read from `APP_VERSION` env var, fallback to `"unknown"`
    - Update `backend/src/apis/inference_api/main.py` FastAPI `version` parameter to read from `APP_VERSION` env var
    - Remove any hardcoded version strings
    - _Requirements: 3.2, 3.3, 3.4, 3.5_

  - [ ]* 2.3 Write unit tests for health endpoint versioning
    - Test `/health` returns version from `APP_VERSION` env var
    - Test `/ping` returns version from `APP_VERSION` env var
    - Test both endpoints return `"unknown"` when env var is not set
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update Dockerfiles and build scripts for version injection
  - [x] 4.1 Add `APP_VERSION` build arg to all three Dockerfiles
    - Add `ARG APP_VERSION=unknown` and `ENV APP_VERSION=${APP_VERSION}` to `backend/Dockerfile.app-api`
    - Add `ARG APP_VERSION=unknown` and `ENV APP_VERSION=${APP_VERSION}` to `backend/Dockerfile.inference-api`
    - Add `ARG APP_VERSION=unknown` and `ENV APP_VERSION=${APP_VERSION}` to `backend/Dockerfile.rag-ingestion`
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [x] 4.2 Update build scripts to pass `--build-arg APP_VERSION`
    - Update `scripts/stack-app-api/build.sh` to read VERSION file and pass `--build-arg APP_VERSION=...`
    - Update `scripts/stack-inference-api/build.sh` to read VERSION file and pass `--build-arg APP_VERSION=...`
    - _Requirements: 4.4_

  - [x] 4.3 Update push-to-ecr scripts for dual-tagging (semver + SHA)
    - Update `scripts/stack-app-api/push-to-ecr.sh` to push both semver and SHA tags
    - Update `scripts/stack-inference-api/push-to-ecr.sh` to push both semver and SHA tags
    - Update `scripts/stack-rag-ingestion/push-to-ecr.sh` to push both semver and SHA tags (if exists)
    - Update SSM parameter writes to store semver tag instead of SHA tag
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 5. Update infrastructure for version tagging and frontend config
  - [x] 5.1 Add `appVersion` to CDK config and `applyStandardTags()`
    - Add `appVersion` field to `AppConfig` interface in `infrastructure/lib/config.ts`
    - Load `appVersion` from `CDK_APP_VERSION` env var or CDK context (`appVersion`) in `loadConfig()`
    - Add `Version` tag in `applyStandardTags()` using `config.appVersion`
    - This automatically tags all resources across all 7 stacks
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 5.2 Update `load-env.sh` and deploy scripts to pass version to CDK
    - Update `scripts/common/load-env.sh` to export `CDK_APP_VERSION` from VERSION file
    - Update all `synth.sh` and `deploy.sh` scripts to pass `--context appVersion=...` to CDK commands
    - _Requirements: 8.5, 8.6_

  - [x] 5.3 Add version to CDK `FrontendStack` config.json generation
    - Update `infrastructure/lib/frontend-stack.ts` to include `version` in the generated `config.json`
    - Read version from `config.appVersion` (already loaded in 5.1)
    - _Requirements: 7.5, 7.6_

- [x] 6. Update frontend to display version
  - [x] 6.1 Add `version` to `RuntimeConfig` and `ConfigService`
    - Add `version` field to `RuntimeConfig` interface in `config.service.ts`
    - Add a `version` computed signal to `ConfigService` that returns the version from config
    - _Requirements: 7.1, 7.2_

  - [x] 6.2 Add version fallbacks to environment files
    - Add `version: 'dev'` to `frontend/ai.client/src/environments/environment.ts`
    - Add `version: ''` to `frontend/ai.client/src/environments/environment.production.ts`
    - _Requirements: 7.3, 7.4_

  - [x] 6.3 Display version in the frontend UI
    - Add version display to a visible location (sidebar footer, header tooltip, or settings page)
    - Read version from `ConfigService.version` signal
    - _Requirements: 7.7_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Update CI/CD workflows for version integration
  - [x] 8.1 Update `app-api.yml` workflow
    - Add step to read VERSION file into `APP_VERSION` output in `build-docker` job
    - Pass `--build-arg APP_VERSION=$APP_VERSION` to Docker build
    - Push both semver and SHA tags to ECR
    - Pass version to CDK deploy via `CDK_APP_VERSION` env var or `--context appVersion`
    - _Requirements: 6.1, 6.4, 6.6_

  - [x] 8.2 Update `inference-api.yml` workflow
    - Add step to read VERSION file into `APP_VERSION` output in `build-docker` job
    - Pass `--build-arg APP_VERSION=$APP_VERSION` to Docker build
    - Push both semver and SHA tags to ECR
    - Pass version to CDK deploy via `CDK_APP_VERSION` env var or `--context appVersion`
    - _Requirements: 6.2, 6.4, 6.6_

  - [x] 8.3 Update `rag-ingestion.yml` workflow
    - Add step to read VERSION file into `APP_VERSION` output in `build-docker` job
    - Pass `--build-arg APP_VERSION=$APP_VERSION` to Docker build
    - Push both semver and SHA tags to ECR
    - _Requirements: 6.3, 6.4_

  - [x] 8.4 Update `frontend.yml` workflow
    - Add step to read VERSION file into `APP_VERSION`
    - Pass version as CDK context (`--context appVersion=$APP_VERSION`) during deploy
    - _Requirements: 6.5_

- [x] 9. Create PR version gate workflow
  - [x] 9.1 Create `.github/workflows/version-check.yml`
    - Trigger on all PRs to `main` with no path filters
    - Fetch `main` branch for comparison
    - Check 1: Fail if VERSION file content is identical to `main` (version not bumped)
    - Check 2: Fail if `sync-version.sh --check` exits non-zero (manifests out of sync)
    - Run both checks regardless of the other's result (not fail-fast)
    - Require no AWS credentials, Docker, or dependency installation (bash + git only)
    - Use a job name suitable for required status check in branch protection
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

- [x] 10. Add git tagging to CI
  - [x] 10.1 Add git tag creation step to the `app-api.yml` workflow (or a dedicated release workflow)
    - After successful deploy on `main`, create annotated git tag `v<VERSION>` if it doesn't exist
    - Tag message: `"Release <VERSION>"`
    - Skip if tag already exists (idempotent)
    - Only run on `main` branch (not `develop` or PR branches)
    - Ensure workflow has `contents: write` permission
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 11. Create AI assistant versioning guides
  - [x] 11.1 Create all three AI assistant guide files
    - Create `.claude/skills/versioning/SKILL.md` with concise version bump instructions
    - Create `.cursor/rules/versioning.mdc` with `alwaysApply: true` frontmatter and concise version bump instructions
    - Create `.kiro/steering/versioning.md` (no frontmatter) with concise version bump instructions
    - All three contain identical core info: VERSION file location, SemVer format, sync script command, PR gate behavior, CI handles the rest
    - Each file under ~20 lines of content
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The design uses Bash, Python, TypeScript, and YAML — no pseudocode language selection needed
- All runtime commands must execute inside the Docker container via `docker compose exec dev`

# Implementation Plan: GitHub Actions Job Summaries

## Overview

Implement a shared bash function library (`scripts/common/summary.sh`) and integrate it into all 10 CI/CD workflows to produce rich, standardized GitHub Actions job summaries. The approach is incremental: build the core library first, then integrate workflow-by-workflow, starting with the simplest cases and building toward the complex nightly aggregator.

## Tasks

- [x] 1. Create the shared summary generator library with core functions
  - [x] 1.1 Create `scripts/common/summary.sh` with `write_header` function
    - Implement `write_header` accepting `workflow_name`, `status` (success|failure|partial), and `stack_name` parameters
    - Read `CDK_PROJECT_PREFIX`, `CDK_AWS_REGION`, `GITHUB_SHA`, `GITHUB_REF_NAME`, `GITHUB_EVENT_NAME`, `GITHUB_ACTOR`, `GITHUB_RUN_ID` from environment
    - Read version from `VERSION` file, extract short commit SHA, first line of commit message
    - Display status emoji (✅/❌/⚠️), environment, region, project prefix, version, branch, trigger type
    - When `GITHUB_EVENT_NAME` is `workflow_dispatch`, display user-provided input parameters from `$GITHUB_EVENT_PATH`
    - Append all output to `$GITHUB_STEP_SUMMARY`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Add `write_collapsible` and `write_cdk_outputs_table` utility functions
    - `write_collapsible` accepts `summary_label` and `content`, wraps in `<details><summary>...</summary>` HTML
    - `write_cdk_outputs_table` accepts a CDK outputs JSON file path, parses with `jq`, renders as a markdown table (Output Key | Value)
    - Wrap output in a collapsible section with descriptive label
    - _Requirements: 8.1, 8.3, 4.9_

  - [x] 1.3 Add `write_timing_footer` function
    - Accept key=value pairs for phase timings (e.g., `install=45` `build=120` `deploy=300`)
    - Display each phase duration in human-readable format (Xm Ys)
    - Display total workflow wall-clock duration using `$SECONDS`
    - _Requirements: 7.1, 7.2_

  - [x] 1.4 Add `write_failure_summary` function
    - Accept `step_name`, `exit_code`, and `log_tail` (last 20 lines) parameters
    - Render failure details inside a collapsible `<details>` section
    - Include step name, exit code, and log output
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 1.5 Add `write_build_summary` function
    - Accept `image_tag`, `platform`, `image_size_bytes`, `ecr_uri`, `image_digest` parameters
    - Read optional `CACHE_HIT_PYTHON` and `CACHE_HIT_NODE` env vars for cache hit/miss reporting
    - Display image metadata in a table: tag, platform, compressed size (human-readable), ECR URI, digest
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 1.6 Add test summary functions: `write_test_summary_python`, `write_test_summary_frontend`, `write_test_summary_cdk`, `write_test_summary_docker`
    - `write_test_summary_python`: accept total, passed, failed, skipped, duration_seconds; optional coverage_percent, failing_test_names (newline-separated, max 10)
    - `write_test_summary_frontend`: accept total_suites, total_tests, passed, failed, duration_seconds; optional coverage_percent
    - `write_test_summary_cdk`: accept result (pass|fail), resource_count
    - `write_test_summary_docker`: accept health_check_result (pass|fail), startup_time_seconds
    - Wrap lists of more than 5 failing test names in a collapsible section
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 8.2_

  - [x] 1.7 Add `write_deploy_summary` function with stack-type dispatch
    - Accept `stack_type` parameter to dispatch to stack-specific formatting
    - Implement sub-formatters for each stack type: `infrastructure`, `app-api`, `inference-api`, `frontend`, `gateway`, `rag-ingestion`, `sagemaker`, `bootstrap`
    - Each sub-formatter extracts relevant fields from CDK outputs JSON or environment variables
    - Infrastructure: VPC ID, ALB ARN, ECS Cluster name, DynamoDB table count, S3 bucket count
    - App API: ECS service/cluster name, task definition revision, image tag, force-new-deployment confirmation
    - Inference API: image tag, SSM parameter path, target platform, AgentCore Runtime update description
    - Frontend: S3 bucket name, CloudFront distribution ID, cache invalidation status, propagation time
    - Gateway: Lambda function count, MCP tool names, API Gateway endpoint URL
    - RAG Ingestion: image tag, target platform, ECS task definition details
    - SageMaker: DynamoDB tables, S3 bucket name, SageMaker execution role ARN
    - Bootstrap: auth provider ID, DynamoDB items written, tables seeded
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

- [x] 2. Checkpoint — Verify shared library
  - Ensure `scripts/common/summary.sh` is syntactically valid (`bash -n scripts/common/summary.sh`)
  - Ensure all functions are defined and sourceable
  - Ask the user if questions arise

- [x] 3. Integrate summaries into `version-check.yml`
  - [x] 3.1 Add `write_version_check_summary` function to `scripts/common/summary.sh`
    - Accept `version_bumped`, `manifests_synced`, `lockfiles_synced` (each pass|fail)
    - Accept optional `old_version` and `new_version` parameters
    - Render a checklist table with pass/fail status per check
    - When any check fails, include remediation instructions (exact commands to run)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 3.2 Update `.github/workflows/version-check.yml` to generate summary
    - Add a summary generation step with `if: always()` after the evaluate-results step
    - Source `scripts/common/summary.sh` and call `write_header` + `write_version_check_summary`
    - Pass step outcomes from existing `version-bumped`, `manifests-synced`, `lockfiles-synced` step IDs
    - Extract old/new version values from VERSION file and `origin/main` for display
    - _Requirements: 6.1, 6.2, 6.3, 9.1, 9.3, 10.3_

- [x] 4. Integrate summaries into `app-api.yml`
  - [x] 4.1 Add summary steps to `build-docker` job in `app-api.yml`
    - Capture `$SECONDS` at job start for timing
    - After Docker build, capture image size via `docker inspect`
    - Add summary step with `if: always()` that sources `summary.sh` and calls `write_header`, `write_build_summary`, `write_timing_footer`
    - On failure, call `write_failure_summary` with relevant error context
    - _Requirements: 2.1, 2.2, 2.3, 7.1, 9.3, 10.2, 10.3_

  - [x] 4.2 Add summary steps to `test-python`, `test-docker`, and `test-cdk` jobs in `app-api.yml`
    - In `test-python`: capture pytest output (total/passed/failed/skipped/duration), call `write_test_summary_python`
    - In `test-docker`: capture health check result and startup time, call `write_test_summary_docker`
    - In `test-cdk`: capture validation result and resource count, call `write_test_summary_cdk`
    - Each test job gets `write_header` + test-specific summary + `write_timing_footer`
    - All summary steps use `if: always()`
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 7.1, 9.3, 10.3_

  - [x] 4.3 Replace existing inline deploy summary in `app-api.yml` with script-based summary
    - Remove the existing inline `Deployment summary` step from `deploy-infrastructure` job
    - Add new summary step: source `summary.sh`, call `write_header`, `write_deploy_summary "app-api"`, `write_cdk_outputs_table`, `write_timing_footer`
    - On failure, call `write_failure_summary`
    - Use `if: always()` condition
    - _Requirements: 4.2, 4.9, 7.1, 8.1, 9.1, 9.3, 10.1, 10.3_

  - [x] 4.4 Add summary step to `push-to-ecr` job in `app-api.yml`
    - After ECR push, call `write_header` and `write_build_summary` with ECR URI and image digest
    - Use `if: always()`
    - _Requirements: 2.2, 9.3, 10.3_

- [x] 5. Integrate summaries into `inference-api.yml`
  - [x] 5.1 Add summary steps to build, test, and deploy jobs in `inference-api.yml`
    - Build job: `write_header` + `write_build_summary` (image tag, platform linux/arm64, image size)
    - Test jobs (test-python, test-docker, test-cdk): appropriate `write_test_summary_*` calls
    - Deploy job: replace existing inline summary with `write_header` + `write_deploy_summary "inference-api"` + `write_cdk_outputs_table` + `write_timing_footer`
    - All summary steps use `if: always()`, call `write_failure_summary` on failure
    - _Requirements: 2.1, 2.2, 3.1, 3.3, 3.4, 4.3, 4.9, 7.1, 9.3, 10.1, 10.3_

- [x] 6. Integrate summaries into `frontend.yml`
  - [x] 6.1 Add summary steps to build, test, and deploy jobs in `frontend.yml`
    - Build job: `write_header` + build metadata (no Docker, but build duration and output size)
    - Test jobs (test-frontend, test-cdk): `write_test_summary_frontend` and `write_test_summary_cdk`
    - Deploy job: replace existing inline summary with `write_header` + `write_deploy_summary "frontend"` + `write_timing_footer`
    - All summary steps use `if: always()`
    - _Requirements: 3.2, 3.3, 4.4, 4.9, 7.1, 9.3, 10.3_

- [x] 7. Integrate summaries into remaining stack workflows
  - [x] 7.1 Add summary steps to `infrastructure.yml`
    - Deploy job: `write_header` + `write_deploy_summary "infrastructure"` + `write_cdk_outputs_table` + `write_timing_footer`
    - Replace existing inline summary, use `if: always()`
    - _Requirements: 4.1, 4.9, 7.1, 9.3, 10.1, 10.3_

  - [x] 7.2 Add summary steps to `gateway.yml`
    - Deploy job: `write_header` + `write_deploy_summary "gateway"` + `write_cdk_outputs_table` + `write_timing_footer`
    - Replace existing inline summary, use `if: always()`
    - _Requirements: 4.5, 4.9, 7.1, 9.3, 10.1, 10.3_

  - [x] 7.3 Add summary steps to `rag-ingestion.yml`
    - Build and deploy jobs: `write_header` + `write_build_summary` + `write_deploy_summary "rag-ingestion"` + `write_cdk_outputs_table` + `write_timing_footer`
    - Replace existing inline summary, use `if: always()`
    - _Requirements: 2.1, 2.2, 4.6, 4.9, 7.1, 9.3, 10.1, 10.3_

  - [x] 7.4 Add summary steps to `sagemaker-fine-tuning.yml`
    - Deploy job: `write_header` + `write_deploy_summary "sagemaker"` + `write_cdk_outputs_table` + `write_timing_footer`
    - Replace existing inline summary, use `if: always()`
    - _Requirements: 4.7, 4.9, 7.1, 9.3, 10.1, 10.3_

  - [x] 7.5 Add summary steps to `bootstrap-data-seeding.yml`
    - Seed job: `write_header` + `write_deploy_summary "bootstrap"` + `write_timing_footer`
    - Replace existing inline summary, use `if: always()`
    - _Requirements: 4.8, 7.1, 9.3, 10.3_

- [x] 8. Checkpoint — Verify all stack workflow integrations
  - Ensure all 8 stack workflows (infrastructure, app-api, inference-api, frontend, gateway, rag-ingestion, sagemaker-fine-tuning, bootstrap-data-seeding) have summary steps
  - Ensure all summary steps use `if: always()` condition
  - Ensure no inline summary markdown remains in any workflow
  - Ensure all workflows source `scripts/common/summary.sh`
  - Ask the user if questions arise

- [x] 9. Integrate summaries into `nightly.yml`
  - [x] 9.1 Add `write_nightly_summary` function to `scripts/common/summary.sh`
    - Accept job results as an array of `name|status|duration` tuples
    - Render a status table with one row per job showing name, status emoji (✅/❌/⏭️), and duration
    - Include a total row with aggregate status and total duration
    - Accept backend and frontend coverage percentages for display
    - Accept smoke test results (endpoints tested, response codes) for display
    - Accept teardown confirmation (stacks destroyed) for display
    - Accept AI coverage analysis summary for display
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 9.2 Add summary steps to individual jobs in `nightly.yml`
    - Add `if: always()` summary steps to: `test-backend`, `test-frontend`, `deploy-*` jobs, `smoke-test`, `teardown`, `ai-coverage-analysis`
    - Each job outputs its status and duration as job outputs for the aggregator
    - Each job also writes its own per-job summary using the appropriate `write_*` functions
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 7.1, 10.3_

  - [x] 9.3 Add a final aggregator job to `nightly.yml`
    - Add a new `summary` job that `needs` all other jobs and runs with `if: always()`
    - Collect job outcomes and durations from job outputs
    - Source `summary.sh`, call `write_header "Nightly Build & Test" <status>`, then `write_nightly_summary` with all job results
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 9.3_

- [x] 10. Final checkpoint — Validate all workflows
  - Ensure all 10 workflows have summary generation steps
  - Ensure `scripts/common/summary.sh` contains all functions from the design: `write_header`, `write_build_summary`, `write_test_summary_python`, `write_test_summary_frontend`, `write_test_summary_cdk`, `write_test_summary_docker`, `write_deploy_summary`, `write_timing_footer`, `write_failure_summary`, `write_collapsible`, `write_cdk_outputs_table`, `write_nightly_summary`, `write_version_check_summary`
  - Ensure all summary steps use `if: always()` condition
  - Ensure no raw JSON dumps remain in deploy summaries (replaced by `write_cdk_outputs_table`)
  - Ensure all requirements (1–10) are covered by at least one task
  - Ask the user if questions arise

## Notes

- All code is bash shell scripting — the shared library and workflow YAML changes
- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The library follows the "Shell Scripts First" convention: YAML stays thin, logic lives in `scripts/`
- All summary steps must use `if: always()` so failed runs still produce diagnostic output

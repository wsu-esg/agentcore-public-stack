# Implementation Plan: Node.js 24 GitHub Actions Upgrade

## Overview

Mechanical upgrade of GitHub Actions third-party action version tags from Node.js 20 to Node.js 24 compatible versions across 10 workflow files and 1 composite action. Each workflow gets action version bumps plus the `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` env var. The composite action gets version bumps only. Property-based tests validate correctness using Python's `hypothesis` library.

## Tasks

- [x] 1. Upgrade composite action (dependency for all workflows)
  - [x] 1.1 Update `.github/actions/configure-aws-credentials/action.yml` to use `aws-actions/configure-aws-credentials@v5`
    - Replace both occurrences of `aws-actions/configure-aws-credentials@v4` with `@v5` (OIDC step and Access Keys step)
    - Preserve all `with:` parameters, `if:` conditions, and step names
    - Do NOT add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` (composite actions don't support top-level `env:`)
    - _Requirements: 3.1, 4.2_

- [x] 2. Upgrade infrastructure and CDK-only workflows
  - [x] 2.1 Update `.github/workflows/infrastructure.yml`
    - Bump `actions/checkout@v4` → `@v5` (all occurrences)
    - Bump `actions/cache/save@v4` → `@v5`, `actions/cache/restore@v4` → `@v5`
    - Bump `actions/upload-artifact@v4` → `@v5`, `actions/download-artifact@v4` → `@v5`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to the top-level `env:` block
    - Preserve all `with:` parameters, `on:` triggers, `needs:`, `concurrency:`, `permissions:`, `environment:` logic
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 2.2 Update `.github/workflows/sagemaker-fine-tuning.yml`
    - Bump `actions/checkout@v4` → `@v5` (all occurrences)
    - Bump `actions/cache/save@v4` → `@v5`, `actions/cache/restore@v4` → `@v5`
    - Bump `actions/upload-artifact@v4` → `@v5`, `actions/download-artifact@v4` → `@v5`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to the top-level `env:` block
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 2.3 Update `.github/workflows/version-check.yml`
    - Bump `actions/checkout@v4` → `@v5`
    - Bump `actions/setup-node@v4` → `@v5`
    - CRITICAL: Preserve `node-version: '22'` in the `actions/setup-node` step — this controls the installed Node.js version, not the action runtime
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` as a new top-level `env:` block (this file currently has no top-level `env:`)
    - _Requirements: 1.1, 1.6, 4.1, 5.1, 6.3, 6.7_

  - [x] 2.4 Update `.github/workflows/bootstrap-data-seeding.yml`
    - Bump `actions/checkout@v4` → `@v5`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` as a new top-level `env:` block (this file currently has no top-level `env:`)
    - _Requirements: 1.1, 4.1, 5.1_

- [x] 3. Checkpoint - Verify composite action and simple workflows
  - Ensure all modified files are valid YAML
  - Grep for any remaining `@v4` references in the files updated so far
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Upgrade Docker-build workflows
  - [x] 4.1 Update `.github/workflows/app-api.yml`
    - Bump `actions/checkout@v4` → `@v5` (all occurrences)
    - Bump `actions/cache/save@v4` → `@v5`, `actions/cache/restore@v4` → `@v5`
    - Bump `actions/upload-artifact@v4` → `@v5`, `actions/download-artifact@v4` → `@v5`
    - Bump `docker/setup-buildx-action@v3` → `@v4`
    - Bump `docker/build-push-action@v6` → `@v7`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to the top-level `env:` block
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 4.1, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 4.2 Update `.github/workflows/inference-api.yml`
    - Bump `actions/checkout@v4` → `@v5` (all occurrences)
    - Bump `actions/cache/save@v4` → `@v5`, `actions/cache/restore@v4` → `@v5`
    - Bump `actions/upload-artifact@v4` → `@v5`, `actions/download-artifact@v4` → `@v5`
    - Bump `docker/setup-buildx-action@v3` → `@v4`
    - Bump `docker/build-push-action@v6` → `@v7`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to the top-level `env:` block
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 4.1, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 4.3 Update `.github/workflows/rag-ingestion.yml`
    - Bump `actions/checkout@v4` → `@v5` (all occurrences)
    - Bump `actions/cache/save@v4` → `@v5`, `actions/cache/restore@v4` → `@v5`
    - Bump `actions/upload-artifact@v4` → `@v5`, `actions/download-artifact@v4` → `@v5`
    - Bump `docker/setup-buildx-action@v3` → `@v4`
    - Bump `docker/build-push-action@v6` → `@v7`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to the top-level `env:` block
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 4.1, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 5. Upgrade remaining workflows (frontend, gateway, nightly)
  - [x] 5.1 Update `.github/workflows/frontend.yml`
    - Bump `actions/checkout@v4` → `@v5` (all occurrences)
    - Bump `actions/cache/save@v4` → `@v5`, `actions/cache/restore@v4` → `@v5`
    - Bump `actions/upload-artifact@v4` → `@v5`, `actions/download-artifact@v4` → `@v5`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to the top-level `env:` block
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 5.2 Update `.github/workflows/gateway.yml`
    - Bump `actions/checkout@v4` → `@v5` (all occurrences)
    - Bump `actions/cache/save@v4` → `@v5`, `actions/cache@v4` → `@v5`
    - Bump `actions/upload-artifact@v4` → `@v5`, `actions/download-artifact@v4` → `@v5`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to the top-level `env:` block
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 5.3 Update `.github/workflows/nightly.yml`
    - Bump `actions/checkout@v4` → `@v5` (all occurrences)
    - Bump `actions/cache/save@v4` → `@v5`, `actions/cache/restore@v4` → `@v5`, `actions/cache@v4` → `@v5`
    - Bump `actions/upload-artifact@v4` → `@v5`, `actions/download-artifact@v4` → `@v5`
    - Bump `actions/setup-python@v5` → `@v6`
    - Bump `docker/setup-buildx-action@v3` → `@v4`
    - Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to the top-level `env:` block
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 4.1, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 6. Checkpoint - Verify all files upgraded
  - Run grep across all `.github/workflows/*.yml` and `.github/actions/**/*.yml` for deprecated version patterns
  - Confirm zero matches for: `actions/checkout@v4`, `actions/cache@v4`, `actions/cache/save@v4`, `actions/cache/restore@v4`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`, `docker/setup-buildx-action@v3`, `docker/build-push-action@v6`, `aws-actions/configure-aws-credentials@v4`
  - Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 7. Write property-based tests
  - [x] 7.1 Create test file `backend/tests/test_nodejs24_actions_upgrade.py` with shared fixtures
    - Create a pytest fixture that loads all 11 target YAML files (10 workflows + 1 composite action)
    - Define the complete list of deprecated version patterns and target version patterns as constants
    - Define the list of workflow files (excluding composite action) for env var tests
    - _Requirements: 4.1, 4.2_

  - [x] 7.2 Write property test: Zero deprecated action version references (Property 1)
    - **Property 1: Zero deprecated action version references**
    - Use `hypothesis` with `@given(sampled_from(all_target_files))` to select a file
    - Parse YAML, extract all `uses:` values, assert none match deprecated patterns
    - Exhaustively verify across all 11 files
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 3.1, 4.1, 4.2, 4.3, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6**

  - [x] 7.3 Write property test: Node.js 24 opt-in flag present in all workflows (Property 2)
    - **Property 2: Node.js 24 opt-in flag present in all workflows**
    - Use `hypothesis` with `@given(sampled_from(workflow_files))` to select a workflow file (10 files, excluding composite action)
    - Parse YAML, check top-level `env:` block contains `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`
    - **Validates: Requirements 5.1**

  - [x] 7.4 Write property test: Workflow structure preservation (Property 3)
    - **Property 3: Workflow structure preservation**
    - Use `hypothesis` with `@given(sampled_from(workflow_files))` to select a workflow file
    - Parse YAML, verify `on:` triggers, `jobs:` keys, `needs:` chains, `concurrency:`, `permissions:`, and `environment:` are present and structurally intact
    - Verify `version-check.yml` still has `node-version: '22'` in the `setup-node` step
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**

- [x] 8. Final checkpoint - Ensure all tests pass
  - Run `python -m pytest backend/tests/test_nodejs24_actions_upgrade.py -v` to verify all property tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The composite action is upgraded first since workflows depend on it
- `version-check.yml` and `bootstrap-data-seeding.yml` need special handling: they have no existing top-level `env:` block, so one must be created
- `gateway.yml` uses `actions/cache@v4` (not `cache/save` or `cache/restore`) in some jobs — all variants must be bumped
- Property tests use Python `hypothesis` library (already installed in the project)
- Git commands run locally on the host machine, NOT in a dev container

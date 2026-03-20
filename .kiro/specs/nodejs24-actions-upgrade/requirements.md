# Requirements Document

## Introduction

GitHub is deprecating Node.js 20 as the runtime for JavaScript-based GitHub Actions. Starting June 2nd, 2026, Node.js 24 becomes the forced default. Every workflow run currently emits deprecation warnings for actions still running on Node.js 20. This feature upgrades all third-party actions across the repository's 10 workflows and 1 custom composite action to versions that ship with Node.js 24 support, and enables the `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` environment variable to opt in early and validate compatibility before the deadline.

## Glossary

- **Workflow**: A GitHub Actions YAML file in `.github/workflows/` that defines a CI/CD pipeline.
- **Composite_Action**: A reusable action defined with `using: 'composite'` in `.github/actions/`, which delegates to shell steps and other actions but does not declare its own Node.js runtime.
- **Third_Party_Action**: A GitHub Action published by an external organization (e.g., `actions/checkout`, `docker/setup-buildx-action`) referenced by `owner/name@version` in workflow `uses:` clauses.
- **Action_Version_Tag**: The `@vN` suffix on a `uses:` reference that pins to a major version of a third-party action (e.g., `@v4`, `@v5`).
- **Node24_Opt_In_Flag**: The `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` environment variable that, when set to `true`, forces all JavaScript actions to run on Node.js 24 before the June 2nd, 2026 deadline.
- **Deprecation_Warning**: The annotation GitHub emits on every workflow run stating "Node.js 20 actions are deprecated."

## Requirements

### Requirement 1: Upgrade GitHub Official Actions to Node.js 24-Compatible Versions

**User Story:** As a DevOps engineer, I want all GitHub official actions upgraded to versions that support Node.js 24, so that workflows stop emitting deprecation warnings and are ready for the June 2nd forced switch.

#### Acceptance Criteria

1. WHEN a workflow references `actions/checkout`, THE Workflow SHALL use `actions/checkout@v5` or a later Node.js 24-compatible version.
2. WHEN a workflow references `actions/cache@v4`, `actions/cache/save@v4`, or `actions/cache/restore@v4`, THE Workflow SHALL use the equivalent `@v5` (or later Node.js 24-compatible) version of each cache action.
3. WHEN a workflow references `actions/upload-artifact@v4`, THE Workflow SHALL use `actions/upload-artifact@v5` or a later Node.js 24-compatible version.
4. WHEN a workflow references `actions/download-artifact@v4`, THE Workflow SHALL use `actions/download-artifact@v5` or a later Node.js 24-compatible version.
5. WHEN a workflow references `actions/setup-python@v5`, THE Workflow SHALL use `actions/setup-python@v6` or a later Node.js 24-compatible version if the current version does not support Node.js 24, or retain `@v5` if it already ships with Node.js 24 support.
6. WHEN a workflow references `actions/setup-node@v4`, THE Workflow SHALL use `actions/setup-node@v5` or a later Node.js 24-compatible version.

### Requirement 2: Upgrade Docker Actions to Node.js 24-Compatible Versions

**User Story:** As a DevOps engineer, I want Docker-related actions upgraded to Node.js 24-compatible versions, so that container build workflows are compatible with the new runtime.

#### Acceptance Criteria

1. WHEN a workflow references `docker/setup-buildx-action@v3`, THE Workflow SHALL use `docker/setup-buildx-action@v4` or a later Node.js 24-compatible version.
2. WHEN a workflow references `docker/build-push-action@v6`, THE Workflow SHALL use `docker/build-push-action@v7` or a later Node.js 24-compatible version if the current version does not support Node.js 24, or retain `@v6` if it already ships with Node.js 24 support.

### Requirement 3: Upgrade AWS Actions to Node.js 24-Compatible Versions

**User Story:** As a DevOps engineer, I want the AWS credential configuration action upgraded to a Node.js 24-compatible version, so that all AWS authentication steps work under the new runtime.

#### Acceptance Criteria

1. WHEN the Composite_Action references `aws-actions/configure-aws-credentials@v4`, THE Composite_Action SHALL use `aws-actions/configure-aws-credentials@v5` or a later Node.js 24-compatible version.

### Requirement 4: Apply Upgrades Across All Workflows

**User Story:** As a DevOps engineer, I want every occurrence of each action updated consistently across all 10 workflows and the composite action, so that no workflow is left running deprecated Node.js 20 actions.

#### Acceptance Criteria

1. THE Upgrade SHALL update action references in all 10 workflow files: `infrastructure.yml`, `app-api.yml`, `inference-api.yml`, `frontend.yml`, `gateway.yml`, `rag-ingestion.yml`, `sagemaker-fine-tuning.yml`, `nightly.yml`, `version-check.yml`, and `bootstrap-data-seeding.yml`.
2. THE Upgrade SHALL update action references in the Composite_Action file `.github/actions/configure-aws-credentials/action.yml`.
3. IF a workflow file contains multiple references to the same action at the old version, THEN THE Upgrade SHALL update every occurrence in that file.

### Requirement 5: Enable Node.js 24 Opt-In for Early Validation

**User Story:** As a DevOps engineer, I want to opt in to Node.js 24 early using the `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` flag, so that I can validate all workflows run correctly on Node.js 24 before GitHub forces the switch.

#### Acceptance Criteria

1. THE Upgrade SHALL add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` as a top-level `env:` variable in each of the 10 workflow files.
2. WHEN the Node24_Opt_In_Flag is set to `true`, THE Workflow SHALL force all JavaScript-based actions in that run to execute on the Node.js 24 runtime.
3. WHILE the Node24_Opt_In_Flag is set to `true` in all workflows, THE Repository SHALL produce zero Deprecation_Warning annotations on workflow runs.

### Requirement 6: Preserve Existing Workflow Behavior

**User Story:** As a DevOps engineer, I want the upgrade to preserve all existing workflow behavior (triggers, job structure, caching, artifact passing, environment selection, concurrency controls), so that the upgrade is a safe, non-breaking change.

#### Acceptance Criteria

1. THE Upgrade SHALL preserve all `on:` trigger configurations (push, pull_request, workflow_dispatch, schedule, workflow_call) in every workflow.
2. THE Upgrade SHALL preserve all job dependency chains (`needs:` declarations) in every workflow.
3. THE Upgrade SHALL preserve all `with:` parameters (paths, keys, retention-days, restore-keys, platforms, build-args, outputs) passed to each action.
4. THE Upgrade SHALL preserve all `concurrency:` group configurations in every workflow.
5. THE Upgrade SHALL preserve all `permissions:` declarations in every workflow.
6. THE Upgrade SHALL preserve all `environment:` selection logic in every workflow.
7. WHEN `actions/setup-node@v4` is upgraded in `version-check.yml`, THE Workflow SHALL continue to set `node-version: '22'` for the project build tools.

### Requirement 7: Verify No Deprecated Node.js 20 Action References Remain

**User Story:** As a DevOps engineer, I want to confirm that no workflow or composite action still references a Node.js 20-only action version after the upgrade, so that the repository is fully prepared for the June 2nd deadline.

#### Acceptance Criteria

1. WHEN the upgrade is complete, THE Repository SHALL contain zero references to `actions/checkout@v4` across all workflow and action YAML files.
2. WHEN the upgrade is complete, THE Repository SHALL contain zero references to `actions/cache@v4`, `actions/cache/save@v4`, or `actions/cache/restore@v4` across all workflow and action YAML files.
3. WHEN the upgrade is complete, THE Repository SHALL contain zero references to `actions/upload-artifact@v4` or `actions/download-artifact@v4` across all workflow and action YAML files.
4. WHEN the upgrade is complete, THE Repository SHALL contain zero references to `actions/setup-node@v4` across all workflow and action YAML files.
5. WHEN the upgrade is complete, THE Repository SHALL contain zero references to `docker/setup-buildx-action@v3` across all workflow and action YAML files.
6. WHEN the upgrade is complete, THE Repository SHALL contain zero references to `aws-actions/configure-aws-credentials@v4` across all workflow and action YAML files.

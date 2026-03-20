# Requirements Document

## Introduction

This feature enhances the GitHub Actions Job Summaries (`$GITHUB_STEP_SUMMARY`) across all CI/CD workflows in the AgentCore Public Stack monorepo. Currently, summaries exist only on the final deploy jobs and are minimal — typically just environment, region, project prefix, and a raw JSON dump of CDK outputs. Several workflows and many intermediate jobs produce no summary at all.

The goal is to make every workflow run produce a rich, visually polished, information-dense summary on the GitHub dashboard — covering build metadata, test results, deployment details, timing, version info, and links — so that developers get a spectacular at-a-glance view of what happened without digging through logs.

### Current State Analysis

| Workflow | Current Summary | Location |
|---|---|---|
| `infrastructure.yml` | Basic deploy details + raw JSON outputs | `deploy` job only |
| `rag-ingestion.yml` | Basic deploy details + image tag + raw JSON outputs | `deploy-infrastructure` job only |
| `inference-api.yml` | Basic deploy details + image tag + raw JSON outputs | `deploy-infrastructure` job only |
| `app-api.yml` | Basic deploy details + image tag + raw JSON outputs | `deploy-infrastructure` and `create-git-tag` jobs |
| `frontend.yml` | Basic deploy details + CloudFront note | `deploy-assets` job only |
| `gateway.yml` | Basic deploy details + resource list + raw JSON outputs | `deploy-stack` job only |
| `sagemaker-fine-tuning.yml` | Basic deploy details + resource list + raw JSON outputs | `deploy` job only |
| `bootstrap-data-seeding.yml` | Minimal 3-line summary | `seed` job only |
| `nightly.yml` | No summary at all | — |
| `version-check.yml` | No summary at all | — |

### Gaps Identified

1. No workflow-level summary that aggregates results across all jobs
2. No build metadata (Docker image size, build duration, cache hit/miss)
3. No test result summaries (pass/fail counts, coverage percentages)
4. No version information (VERSION file content, git SHA, previous version)
5. No timing information (job durations, total pipeline time)
6. No visual structure (no emojis for status, no tables, no collapsible sections)
7. No links to artifacts, ECR images, or CloudFormation stacks
8. Nightly workflow has zero summary despite being the most complex pipeline
9. Version-check workflow has no summary despite being a PR gate

## Glossary

- **Job_Summary**: The markdown content written to `$GITHUB_STEP_SUMMARY` in a GitHub Actions workflow step, rendered on the GitHub Actions run dashboard page
- **Summary_Generator_Script**: A shell script in `scripts/common/` that generates standardized Job_Summary markdown content for a given workflow
- **Workflow**: A GitHub Actions YAML file in `.github/workflows/` that defines a CI/CD pipeline
- **Stack**: A CDK-defined set of AWS resources deployed by a single workflow (e.g., AppApiStack, InferenceApiStack)
- **Deploy_Job**: The final job in a deployment workflow that runs `cdk deploy` and triggers service updates
- **Build_Job**: A job that compiles code or builds Docker images
- **Test_Job**: A job that runs unit tests, integration tests, or CDK validation
- **Nightly_Workflow**: The `nightly.yml` workflow that runs a full deploy-test-teardown cycle on a schedule
- **Version_Check_Workflow**: The `version-check.yml` workflow that validates VERSION file changes on PRs to main

## Requirements

### Requirement 1: Standardized Summary Header

**User Story:** As a developer, I want every workflow summary to start with a consistent header showing the workflow name, status, and key metadata, so that I can immediately identify what ran and whether it succeeded.

#### Acceptance Criteria

1. THE Summary_Generator_Script SHALL produce a header section containing the workflow display name, a status emoji (✅ for success, ❌ for failure, ⚠️ for partial), the environment name, the AWS region, and the project prefix
2. THE Summary_Generator_Script SHALL include the application version from the VERSION file, the git commit SHA (short form), the branch name, and the commit message (first line) in the header section
3. THE Summary_Generator_Script SHALL include the workflow trigger type (push, pull_request, workflow_dispatch, schedule) in the header section
4. WHEN a workflow is triggered by workflow_dispatch, THE Summary_Generator_Script SHALL display the user-provided input parameters in the header section

### Requirement 2: Build Job Summaries for Docker Workflows

**User Story:** As a developer, I want build jobs to report Docker image metadata in the summary, so that I can verify the correct image was built and track image sizes over time.

#### Acceptance Criteria

1. WHEN a Docker image build completes successfully, THE Build_Job SHALL write to the Job_Summary the image tag, the target platform (e.g., linux/arm64), and the compressed image size in human-readable format
2. WHEN a Docker image is pushed to ECR, THE Build_Job SHALL write to the Job_Summary the full ECR repository URI and the image digest (SHA256)
3. WHEN dependency caching is used, THE Build_Job SHALL report whether the cache was a hit or miss for each cache key (Python packages, node_modules)

### Requirement 3: Test Job Summaries

**User Story:** As a developer, I want test jobs to report pass/fail counts and coverage in the summary, so that I can see test health without opening log files.

#### Acceptance Criteria

1. WHEN Python tests complete, THE Test_Job SHALL write to the Job_Summary the total number of tests, the number passed, the number failed, the number skipped, and the test duration
2. WHEN frontend tests complete, THE Test_Job SHALL write to the Job_Summary the total number of test suites, the number of tests passed, the number failed, and the test duration
3. WHEN CDK validation completes, THE Test_Job SHALL write to the Job_Summary the validation result (pass/fail) and the number of CloudFormation resources in the synthesized template
4. WHEN Docker image tests complete, THE Test_Job SHALL write to the Job_Summary the health check result and the container startup time
5. IF any test job fails, THEN THE Test_Job SHALL write to the Job_Summary a summary of the failure including the failing test names (up to 10)

### Requirement 4: Deploy Job Summaries for All Stacks

**User Story:** As a developer, I want deploy job summaries to show rich deployment details specific to each stack type, so that I can verify the deployment completed correctly and see what changed.

#### Acceptance Criteria

1. WHEN the Infrastructure stack deploys successfully, THE Deploy_Job SHALL write to the Job_Summary a resources table listing VPC ID, ALB ARN, ECS Cluster name, number of DynamoDB tables created, and number of S3 buckets created, extracted from the CDK outputs file
2. WHEN the App API stack deploys successfully, THE Deploy_Job SHALL write to the Job_Summary the ECS service name, the ECS cluster name, the task definition revision, the Docker image tag, and confirmation that force-new-deployment was triggered
3. WHEN the Inference API stack deploys successfully, THE Deploy_Job SHALL write to the Job_Summary the Docker image tag, the SSM parameter path that was updated, the target platform (linux/arm64), and the AgentCore Runtime update mechanism description
4. WHEN the Frontend stack deploys successfully, THE Deploy_Job SHALL write to the Job_Summary the S3 bucket name, the CloudFront distribution ID, whether cache invalidation was triggered, and the estimated propagation time
5. WHEN the Gateway stack deploys successfully, THE Deploy_Job SHALL write to the Job_Summary the number of Lambda functions deployed, the list of MCP tool names, and the API Gateway endpoint URL if available from CDK outputs
6. WHEN the RAG Ingestion stack deploys successfully, THE Deploy_Job SHALL write to the Job_Summary the Docker image tag, the target platform, and the ECS task definition details extracted from CDK outputs
7. WHEN the SageMaker Fine-Tuning stack deploys successfully, THE Deploy_Job SHALL write to the Job_Summary the list of DynamoDB tables, the S3 bucket name, and the SageMaker execution role ARN extracted from CDK outputs
8. WHEN the Bootstrap Data Seeding workflow completes, THE Deploy_Job SHALL write to the Job_Summary the auth provider ID that was seeded, the number of DynamoDB items written, and the tables that were seeded
9. THE Deploy_Job SHALL render CDK stack outputs in a formatted markdown table instead of a raw JSON code block

### Requirement 5: Nightly Workflow Summary

**User Story:** As a developer, I want the nightly workflow to produce a comprehensive summary of the entire deploy-test-teardown cycle, so that I can review nightly health at a glance each morning.

#### Acceptance Criteria

1. THE Nightly_Workflow SHALL produce a Job_Summary containing a status table with one row per job showing the job name, status (pass/fail/skip), and duration
2. WHEN backend tests complete in the nightly workflow, THE Nightly_Workflow SHALL include the backend test coverage percentage in the Job_Summary
3. WHEN frontend tests complete in the nightly workflow, THE Nightly_Workflow SHALL include the frontend test coverage percentage in the Job_Summary
4. WHEN the smoke test job completes, THE Nightly_Workflow SHALL include the smoke test results (endpoints tested, response codes) in the Job_Summary
5. WHEN the teardown job completes, THE Nightly_Workflow SHALL include confirmation of which stacks were destroyed in the Job_Summary
6. WHEN the AI coverage analysis job completes, THE Nightly_Workflow SHALL include a summary of coverage gaps identified in the Job_Summary

### Requirement 6: Version Check Workflow Summary

**User Story:** As a developer, I want the version-check workflow to produce a clear summary showing which checks passed and which failed, so that I can fix version issues quickly on PRs.

#### Acceptance Criteria

1. THE Version_Check_Workflow SHALL produce a Job_Summary containing a checklist table with rows for: VERSION file bumped, manifests in sync, and lockfiles in sync, each showing pass or fail status
2. WHEN the VERSION file has been bumped, THE Version_Check_Workflow SHALL display the old version (from main) and the new version (from the PR branch) in the Job_Summary
3. IF any version check fails, THEN THE Version_Check_Workflow SHALL include remediation instructions in the Job_Summary explaining the exact commands to run

### Requirement 7: Pipeline Timing Information

**User Story:** As a developer, I want to see how long each phase of the pipeline took, so that I can identify bottlenecks and track pipeline performance over time.

#### Acceptance Criteria

1. THE Summary_Generator_Script SHALL capture and display the start time and end time for each major phase (install, build, test, synth, deploy) in the Job_Summary
2. THE Summary_Generator_Script SHALL display the total workflow wall-clock duration in the Job_Summary footer

### Requirement 8: Collapsible Detail Sections

**User Story:** As a developer, I want verbose details (like full CDK outputs or test logs) to be in collapsible sections, so that the summary is scannable but I can drill into details when needed.

#### Acceptance Criteria

1. THE Summary_Generator_Script SHALL wrap CDK stack outputs JSON in a collapsible `<details>` HTML element with a descriptive `<summary>` label
2. THE Summary_Generator_Script SHALL wrap lists of more than 5 items (e.g., test failures, resource lists) in a collapsible `<details>` HTML element
3. THE Summary_Generator_Script SHALL keep the top-level summary content (header, status table, key metrics) always visible without requiring expansion

### Requirement 9: Script-Based Summary Generation

**User Story:** As a developer, I want summary generation logic to live in reusable shell scripts rather than inline YAML, so that summaries are consistent across workflows and maintainable.

#### Acceptance Criteria

1. THE Summary_Generator_Script SHALL be implemented as one or more shell scripts in the `scripts/common/` directory
2. THE Summary_Generator_Script SHALL accept parameters for stack name, environment, region, project prefix, and status to generate the appropriate summary content
3. THE Summary_Generator_Script SHALL be callable from any workflow YAML file with a single `bash` invocation
4. WHEN a new stack workflow is added, THE Summary_Generator_Script SHALL support generating a summary for the new stack without modifying the shared script, by accepting stack-specific data as parameters or environment variables

### Requirement 10: Failure Summaries

**User Story:** As a developer, I want failed workflow runs to still produce a useful summary showing what failed and where, so that I can diagnose issues without scrolling through logs.

#### Acceptance Criteria

1. WHEN a deploy job fails, THE Deploy_Job SHALL write to the Job_Summary the step that failed, the exit code, and the last 20 lines of relevant log output in a collapsible section
2. WHEN a build job fails, THE Build_Job SHALL write to the Job_Summary the build step that failed and the error message
3. THE Summary_Generator_Script SHALL use the `if: always()` condition on summary steps so that summaries are generated for both successful and failed runs

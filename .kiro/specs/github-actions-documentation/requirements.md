# Requirements Document

## Introduction

This document specifies the requirements for creating comprehensive documentation of GitHub Actions configuration for the AgentCore Public Stack project. The documentation will help developers understand what GitHub Variables and Secrets are required for each of the 5 stack deployment workflows.

## Glossary

- **GitHub_Variables**: Non-sensitive configuration values stored in GitHub repository settings, accessed via `vars.*` in workflows
- **GitHub_Secrets**: Sensitive configuration values stored encrypted in GitHub repository settings, accessed via `secrets.*` in workflows
- **Workflow**: A GitHub Actions YAML file that defines CI/CD automation for a specific stack
- **Stack**: A deployable unit of infrastructure (Infrastructure, App API, Inference API, Frontend, or Gateway)
- **Documentation_System**: The README file that will contain the configuration reference

## Requirements

### Requirement 1: Document Structure

**User Story:** As a developer, I want a well-organized documentation structure, so that I can quickly find configuration information for any stack.

#### Acceptance Criteria

1. THE Documentation_System SHALL create a file at `.github/README-ACTIONS.md`
2. THE Documentation_System SHALL include exactly one section titled "GitHub Variables and Secrets"
3. WITHIN the "GitHub Variables and Secrets" section, THE Documentation_System SHALL create exactly 5 subsections, one for each workflow
4. THE Documentation_System SHALL name subsections as: "Infrastructure Stack", "App API Stack", "Inference API Stack", "Frontend Stack", and "Gateway Stack"
5. THE Documentation_System SHALL use a consistent format across all subsections

### Requirement 2: Variable and Secret Extraction

**User Story:** As a developer, I want complete information about all configuration values, so that I can properly configure GitHub Actions for deployment.

#### Acceptance Criteria

1. FOR EACH workflow file, THE Documentation_System SHALL extract all variables referenced via `vars.*` syntax
2. FOR EACH workflow file, THE Documentation_System SHALL extract all secrets referenced via `secrets.*` syntax
3. THE Documentation_System SHALL preserve the exact name as it appears in the workflow (e.g., `AWS_REGION`, `CDK_AWS_ACCOUNT`)
4. THE Documentation_System SHALL identify the type of each configuration value (Variable or Secret)
5. THE Documentation_System SHALL analyze all job steps and environment blocks to find all configuration references

### Requirement 3: Requirement Status Classification

**User Story:** As a developer, I want to know which configuration values are required versus optional, so that I can prioritize my setup work and know what I must provide.

#### Acceptance Criteria

1. FOR EACH configuration value, THE Documentation_System SHALL classify it as either "Required" or "Optional"
2. WHEN a configuration value has no default value AND the downstream resource (in CDK stack or script) requires that value, THE Documentation_System SHALL mark it as "Required"
3. WHEN a configuration value has a default value OR the downstream resource can function without it, THE Documentation_System SHALL mark it as "Optional"
4. THE Documentation_System SHALL use AWS MCP tools to check AWS resource documentation for required parameters when determining requirement status
5. THE Documentation_System SHALL trace configuration values from workflow through scripts to CDK stacks to determine if the final resource requires the value
6. THE Documentation_System SHALL clearly indicate the Required/Optional status in the documentation format

### Requirement 4: Default Value Documentation

**User Story:** As a developer, I want to see default values for configuration items, so that I understand what happens when I don't provide a value.

#### Acceptance Criteria

1. FOR EACH configuration value, THE Documentation_System SHALL identify if a default value exists
2. WHEN a default value is specified in the workflow YAML, THE Documentation_System SHALL document that default value
3. WHEN a default value is specified in `scripts/common/load-env.sh`, THE Documentation_System SHALL document that default value
4. WHEN a default value is specified in `infrastructure/lib/config.ts`, THE Documentation_System SHALL document that default value
5. WHEN a default value is specified in `infrastructure/cdk.context.json`, THE Documentation_System SHALL document that default value
6. WHEN no default value exists in any of these locations, THE Documentation_System SHALL indicate "None" or leave the default field empty
7. THE Documentation_System SHALL display default values in a clear, readable format

### Requirement 5: Purpose Description

**User Story:** As a developer, I want to understand what each configuration value does, so that I can set appropriate values for my environment.

#### Acceptance Criteria

1. FOR EACH configuration value, THE Documentation_System SHALL provide a short description of its purpose
2. THE Description SHALL explain what the configuration value controls or affects
3. THE Description SHALL be concise (typically one sentence)
4. THE Description SHALL use clear, non-technical language where possible
5. WHEN a configuration value affects multiple resources, THE Description SHALL mention the primary use case

### Requirement 6: Consistent Formatting

**User Story:** As a developer, I want consistent formatting across all stack sections, so that I can quickly scan and compare configurations.

#### Acceptance Criteria

1. THE Documentation_System SHALL use either a table format or structured list format for all configuration entries
2. THE Format SHALL be identical across all 5 stack subsections
3. WHEN using table format, THE Documentation_System SHALL include columns for: Name, Type, Required/Optional, Default, and Description
4. WHEN using list format, THE Documentation_System SHALL include all the same information fields in a consistent order
5. THE Documentation_System SHALL use markdown formatting for readability

### Requirement 7: Infrastructure Stack Configuration

**User Story:** As a developer, I want complete documentation of Infrastructure Stack configuration, so that I can deploy the foundation layer.

#### Acceptance Criteria

1. THE Documentation_System SHALL document all variables from `infrastructure.yml` workflow
2. THE Documentation_System SHALL document all secrets from `infrastructure.yml` workflow
3. THE Documentation_System SHALL include configuration values used in synth, test, and deploy jobs
4. THE Documentation_System SHALL identify VPC, networking, and ALB-related configuration
5. THE Documentation_System SHALL document authentication-related configuration (AWS credentials, role ARNs)

### Requirement 8: App API Stack Configuration

**User Story:** As a developer, I want complete documentation of App API Stack configuration, so that I can deploy the application backend service.

#### Acceptance Criteria

1. THE Documentation_System SHALL document all variables from `app-api.yml` workflow
2. THE Documentation_System SHALL document all secrets from `app-api.yml` workflow
3. THE Documentation_System SHALL include Docker image configuration
4. THE Documentation_System SHALL include ECS task configuration (CPU, memory, desired count)
5. THE Documentation_System SHALL include authentication configuration (Entra ID client, tenant, redirect URI)

### Requirement 9: Inference API Stack Configuration

**User Story:** As a developer, I want complete documentation of Inference API Stack configuration, so that I can deploy the Bedrock AgentCore Runtime.

#### Acceptance Criteria

1. THE Documentation_System SHALL document all variables from `inference-api.yml` workflow
2. THE Documentation_System SHALL document all secrets from `inference-api.yml` workflow
3. THE Documentation_System SHALL include runtime environment configuration (log level, directories, URLs)
4. THE Documentation_System SHALL include API key configuration (Tavily, Nova Act)
5. THE Documentation_System SHALL include GPU and resource configuration options

### Requirement 10: Frontend Stack Configuration

**User Story:** As a developer, I want complete documentation of Frontend Stack configuration, so that I can deploy the Angular application.

#### Acceptance Criteria

1. THE Documentation_System SHALL document all variables from `frontend.yml` workflow
2. THE Documentation_System SHALL document all secrets from `frontend.yml` workflow
3. THE Documentation_System SHALL include CloudFront configuration (domain, price class, Route53)
4. THE Documentation_System SHALL include S3 bucket configuration
5. THE Documentation_System SHALL include certificate configuration for HTTPS

### Requirement 11: Gateway Stack Configuration

**User Story:** As a developer, I want complete documentation of Gateway Stack configuration, so that I can deploy the Bedrock AgentCore Gateway and Lambda tools.

#### Acceptance Criteria

1. THE Documentation_System SHALL document all variables from `gateway.yml` workflow
2. THE Documentation_System SHALL document all secrets from `gateway.yml` workflow
3. THE Documentation_System SHALL include API Gateway configuration (type, throttling, WAF)
4. THE Documentation_System SHALL include Lambda function configuration
5. THE Documentation_System SHALL include logging configuration

### Requirement 12: Scope Limitation

**User Story:** As a developer, I want focused documentation on configuration only, so that I'm not overwhelmed with unnecessary information.

#### Acceptance Criteria

1. THE Documentation_System SHALL NOT document workflow architecture or job structure
2. THE Documentation_System SHALL NOT document deployment processes or procedures
3. THE Documentation_System SHALL NOT document script implementations
4. THE Documentation_System SHALL NOT document CDK stack details
5. THE Documentation_System SHALL focus exclusively on GitHub Variables and Secrets configuration

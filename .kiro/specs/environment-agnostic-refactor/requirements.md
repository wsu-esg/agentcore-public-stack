# Requirements Document: Environment-Agnostic Refactoring

## Introduction

This specification defines the requirements for refactoring the AgentCore Public Stack application from an environment-aware codebase to a fully configuration-driven, environment-agnostic architecture. The refactoring will eliminate hardcoded environment logic (dev/test/prod conditionals) and replace it with explicit configuration parameters that can be set externally via GitHub Variables, environment variables, or CDK context.

The goal is to make the codebase simple and accessible for open-source users deploying a single environment while maintaining the ability for the internal development team to manage multiple environments (dev/staging/prod) through GitHub Environments without code changes.

## Glossary

- **Environment-Agnostic Code**: Code that contains no knowledge of deployment environments (dev, test, prod) and makes no decisions based on environment names
- **Configuration-Driven**: An approach where all environment-specific behavior is controlled by external configuration rather than code logic
- **GitHub Environment**: A GitHub feature that allows setting environment-specific variables and secrets with optional protection rules
- **CDK Context**: Configuration values passed to AWS CDK applications via command-line parameters or cdk.json
- **Removal Policy**: AWS CDK setting that determines whether resources are retained or deleted when a stack is destroyed
- **Resource Naming**: The pattern used to generate AWS resource names (e.g., VPCs, DynamoDB tables, S3 buckets)
- **CORS Origins**: Cross-Origin Resource Sharing allowed origins for API endpoints
- **ECS Exec**: AWS ECS feature that allows debugging by executing commands in running containers
- **Project Prefix**: A string prepended to all AWS resource names to ensure uniqueness and identify ownership
- **Retention Flag**: A boolean configuration option that determines whether data resources should be retained on stack deletion

## Requirements

### Requirement 1: Remove Environment Parameter from CDK Configuration

**User Story:** As an open-source user, I want to deploy the application without understanding environment concepts, so that I can get started quickly with minimal configuration.

#### Acceptance Criteria

1. THE CDK Configuration SHALL NOT contain an `environment` field in the `AppConfig` interface
2. THE CDK Configuration SHALL NOT accept an `environment` parameter from CDK context or environment variables
3. WHEN loading configuration, THE System SHALL NOT reference `DEPLOY_ENVIRONMENT` variable
4. THE CDK Configuration SHALL provide explicit boolean and string configuration options instead of environment-based conditionals

### Requirement 2: Implement Configuration-Driven Resource Naming

**User Story:** As a user, I want to control resource naming through a single configuration variable, so that I can deploy multiple instances without name conflicts.

#### Acceptance Criteria

1. THE Resource Naming Function SHALL use the `projectPrefix` value directly without appending environment suffixes
2. WHEN generating resource names, THE System SHALL concatenate `projectPrefix` with resource-specific parts using hyphens
3. THE System SHALL NOT add `-dev`, `-test`, or `-prod` suffixes automatically
4. WHEN users want environment-specific naming, THE System SHALL allow them to include the environment in the `projectPrefix` value itself (e.g., "myproject-dev")

### Requirement 3: Replace Environment Conditionals with Explicit Configuration Flags

**User Story:** As a developer, I want explicit configuration options for resource behavior, so that I can make informed decisions about retention and security settings.

#### Acceptance Criteria

1. THE CDK Configuration SHALL provide a `retainDataOnDelete` boolean flag to control removal policies
2. WHEN `retainDataOnDelete` is true, THE System SHALL set removal policies to RETAIN for data resources (DynamoDB tables, S3 buckets)
3. WHEN `retainDataOnDelete` is false, THE System SHALL set removal policies to DESTROY and enable `autoDeleteObjects` for S3 buckets
4. THE System SHALL NOT use `config.environment === 'prod'` or similar conditionals anywhere in the codebase

### Requirement 4: Implement Configuration-Driven CORS Settings

**User Story:** As a user, I want to specify allowed CORS origins through configuration, so that I can control API access without modifying code.

#### Acceptance Criteria

1. THE System SHALL load CORS origins from configuration variables
2. WHEN no CORS origins are specified, THE System SHALL use `http://localhost:4200` as the default for local development
3. THE System SHALL NOT have hardcoded production or development CORS origins in the code
4. WHEN multiple CORS origins are provided, THE System SHALL accept them as a comma-separated string

### Requirement 5: Remove DEPLOY_ENVIRONMENT Variable from Scripts

**User Story:** As a maintainer, I want to simplify deployment scripts by removing unused environment variables, so that the deployment process is clearer and less error-prone.

#### Acceptance Criteria

1. THE Deployment Scripts SHALL NOT export or reference `DEPLOY_ENVIRONMENT` variable
2. THE CDK Synthesis Commands SHALL NOT pass `--context environment="${DEPLOY_ENVIRONMENT}"`
3. THE Deployment Scripts SHALL pass explicit configuration flags as CDK context parameters
4. WHEN loading environment configuration, THE Scripts SHALL use specific variable names (e.g., `CDK_RETAIN_DATA_ON_DELETE`, `CDK_ENABLE_ECS_EXEC`)

### Requirement 6: Implement Build-Time Configuration Injection for Frontend

**User Story:** As a user, I want frontend API URLs to be configurable at build time, so that I can deploy to different environments without hardcoding URLs.

#### Acceptance Criteria

1. THE Frontend Build Process SHALL support environment variable substitution in configuration files
2. THE Frontend SHALL use a single environment configuration template with placeholder variables
3. WHEN building the frontend, THE System SHALL replace placeholders with values from environment variables
4. THE Frontend Configuration SHALL support variables for `appApiUrl`, `inferenceApiUrl`, and `enableAuthentication`
5. THE Frontend SHALL NOT contain separate `environment.development.ts` or `environment.production.ts` files with hardcoded URLs

### Requirement 7: Update CDK Configuration Loading

**User Story:** As a developer, I want CDK configuration to be loaded from explicit environment variables, so that I can see exactly what configuration is being used.

#### Acceptance Criteria

1. THE CDK Configuration Loader SHALL read configuration from environment variables with `CDK_` prefix
2. THE CDK Configuration Loader SHALL provide a `parseBooleanEnv()` helper function for boolean flags
3. WHEN a boolean environment variable is not set, THE System SHALL use sensible defaults (e.g., `retainDataOnDelete` defaults to true)
4. THE CDK Configuration SHALL validate that required variables are present before deployment
5. THE CDK Configuration SHALL log loaded configuration values for debugging purposes

### Requirement 8: Document Configuration Options for Open-Source Users

**User Story:** As an open-source user, I want clear documentation on required configuration variables, so that I can deploy the application successfully.

#### Acceptance Criteria

1. THE Documentation SHALL list all required GitHub Variables and Secrets for deployment
2. THE Documentation SHALL provide example values for each configuration variable
3. THE Documentation SHALL explain the purpose and impact of each configuration flag
4. THE Documentation SHALL include a "Quick Start" section for single-environment deployment
5. THE Documentation SHALL include an "Advanced" section for multi-environment deployment using GitHub Environments

### Requirement 9: Support GitHub Environments for Multi-Environment Deployments

**User Story:** As a team member, I want to use GitHub Environments to manage dev/staging/prod deployments, so that I can maintain separate environments without code changes.

#### Acceptance Criteria

1. THE GitHub Actions Workflows SHALL support the `environment` key to reference GitHub Environments
2. WHEN a workflow runs, THE System SHALL load variables and secrets from the specified GitHub Environment
3. THE Workflows SHALL support manual environment selection via `workflow_dispatch` inputs
4. THE Workflows SHALL support automatic environment selection based on branch (e.g., `main` → production, `develop` → development)
5. THE Documentation SHALL explain how to create and configure GitHub Environments

### Requirement 10: Remove Environment-Specific Logic from All CDK Stacks

**User Story:** As a maintainer, I want all CDK stacks to be environment-agnostic, so that the infrastructure code is simple and predictable.

#### Acceptance Criteria

1. THE Infrastructure Stack SHALL NOT contain `config.environment === 'prod'` conditionals
2. THE App API Stack SHALL NOT contain environment-based removal policy logic
3. THE Inference API Stack SHALL NOT contain environment-based configuration
4. THE Frontend Stack SHALL NOT contain environment-based CORS or domain logic
5. THE Gateway Stack SHALL NOT contain environment-based configuration
6. WHEN reviewing CDK code, THE System SHALL have zero references to `config.environment` property

### Requirement 11: Validate Configuration at Deployment Time

**User Story:** As a user, I want to receive clear error messages if required configuration is missing, so that I can fix issues before deployment fails.

#### Acceptance Criteria

1. WHEN required configuration variables are missing, THE System SHALL throw an error with a descriptive message
2. THE Error Message SHALL list the missing variable names and their expected format
3. THE System SHALL validate boolean flags are valid boolean strings ("true", "false", "1", "0")
4. THE System SHALL validate AWS account IDs are 12-digit numbers
5. THE System SHALL validate AWS regions are valid region codes

### Requirement 12: Provide Migration Guide for Existing Deployments

**User Story:** As a team member, I want a step-by-step migration guide, so that I can safely migrate existing deployments to the new configuration approach.

#### Acceptance Criteria

1. THE Migration Guide SHALL list all configuration variables that need to be created
2. THE Migration Guide SHALL provide a mapping from old environment-based behavior to new configuration flags
3. THE Migration Guide SHALL include a checklist of code changes required
4. THE Migration Guide SHALL explain how to test the migration in a non-production environment first
5. THE Migration Guide SHALL document rollback procedures if issues occur

### Requirement 13: Update All Deployment Scripts

**User Story:** As a user, I want deployment scripts to use the new configuration approach, so that deployments are consistent and predictable.

#### Acceptance Criteria

1. THE `load-env.sh` Script SHALL NOT export `DEPLOY_ENVIRONMENT` variable
2. THE CDK Deployment Scripts SHALL pass explicit configuration flags as context parameters
3. THE Frontend Build Scripts SHALL support environment variable substitution
4. THE Scripts SHALL validate required environment variables are set before proceeding
5. THE Scripts SHALL provide helpful error messages when configuration is missing

### Requirement 14: Remove Environment Files from Frontend

**User Story:** As a frontend developer, I want a single environment configuration file, so that I don't have to maintain multiple files with duplicated settings.

#### Acceptance Criteria

1. THE Frontend SHALL have a single `environment.ts` file with localhost defaults for local development
2. THE Frontend SHALL NOT have `environment.development.ts` or `environment.production.ts` files
3. WHEN building for deployment, THE System SHALL inject configuration values into the environment file
4. THE Frontend Build Process SHALL use `envsubst` or similar tool for variable substitution
5. THE Frontend SHALL validate that required configuration values are present at runtime

# Runtime Configuration Feature - Requirements

## Overview

Replace build-time environment configuration with runtime configuration to enable environment-agnostic frontend builds and eliminate manual GitHub Actions configuration steps.

## Problem Statement

Currently, the frontend build process requires:
1. Deploy App API and Inference API stacks
2. Manually extract output values (ALB URL, Runtime endpoint URL)
3. Set these values in GitHub Actions secrets/variables
4. Deploy frontend with baked-in environment URLs

This creates:
- Manual intervention in deployment pipeline
- Environment-specific builds (can't reuse builds across environments)
- Tight coupling between infrastructure deployment and frontend build
- Risk of configuration drift and human error

## Goals

1. **Eliminate manual configuration steps** - No manual extraction of URLs or GitHub Actions updates
2. **Environment-agnostic builds** - Build once, deploy to any environment
3. **Maintain CDK patterns** - Infrastructure values flow through SSM/CloudFormation outputs
4. **Zero application downtime** - Configuration updates don't require rebuilds
5. **Developer experience** - Local development remains simple and intuitive

## User Stories

### US-1: As a DevOps engineer, I want frontend deployments to be fully automated
**Acceptance Criteria:**
- Frontend deployment requires no manual URL configuration
- GitHub Actions workflow deploys frontend without hardcoded environment values
- Configuration values are sourced from infrastructure stack outputs
- Deployment succeeds even if backend URLs change

### US-2: As a developer, I want to build the frontend once and deploy to multiple environments
**Acceptance Criteria:**
- Frontend build artifacts contain no environment-specific URLs
- Same build can be deployed to dev, staging, and production
- Environment selection happens at deployment time, not build time
- No rebuild required when backend URLs change

### US-3: As a frontend application, I want to fetch configuration at startup
**Acceptance Criteria:**
- Application fetches `config.json` before initializing
- Configuration includes all required backend URLs
- Application handles configuration fetch failures gracefully
- Configuration is cached for the session duration

### US-4: As an infrastructure engineer, I want configuration to be generated from CDK stack outputs
**Acceptance Criteria:**
- Frontend CDK stack reads values from SSM parameters
- `config.json` is generated during frontend stack deployment
- Configuration includes: App API URL, Inference API Runtime URL
- Configuration is deployed to S3/CloudFront alongside static assets

### US-5: As a developer, I want local development to work without AWS infrastructure
**Acceptance Criteria:**
- Local `config.json` can be created manually for development
- Application falls back to environment.ts values if config.json unavailable
- Clear documentation for local development setup
- No AWS credentials required for local frontend development

## Configuration Schema

### config.json Structure
```json
{
  "appApiUrl": "https://api.example.com",
  "inferenceApiUrl": "https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/...",
  "enableAuthentication": true,
  "environment": "production"
}
```

### Required Configuration Values
- `appApiUrl` - App API backend URL (from ALB)
- `inferenceApiUrl` - AgentCore Runtime endpoint URL
- `enableAuthentication` - Whether to enforce authentication
- `environment` - Environment identifier (dev/staging/production)

## Technical Approach

### 1. Frontend Stack Changes
- Read backend URLs from SSM parameters at synth time
- Generate `config.json` with resolved values
- Deploy `config.json` to S3 bucket alongside static assets
- Ensure `config.json` is served with appropriate cache headers

### 2. Angular Application Changes
- Create `ConfigService` to fetch and store runtime configuration
- Implement `APP_INITIALIZER` to load config before app bootstrap
- Update existing services to use `ConfigService` instead of environment.ts
- Maintain backward compatibility with environment.ts for local dev

### 3. Infrastructure Changes
- App API stack exports ALB URL to SSM
- Inference API stack exports Runtime endpoint URL to SSM
- Frontend stack imports these values and generates config.json
- CloudFront serves config.json with short cache TTL

### 4. Deployment Pipeline Changes
- Remove manual URL configuration from GitHub Actions
- Frontend deployment depends on backend stack completion
- No environment-specific build steps required

## Non-Goals

- Dynamic configuration updates without redeployment (future enhancement)
- Configuration versioning or rollback (use CloudFormation rollback)
- Multi-region configuration (single region per deployment)
- Configuration encryption (URLs are not sensitive)

## Success Metrics

- Zero manual steps in deployment pipeline
- Frontend build time reduced (no environment-specific builds)
- Deployment reliability improved (no human error in URL configuration)
- Time to deploy new environment reduced by 50%

## Dependencies

- App API stack must export ALB URL to SSM
- Inference API stack must export Runtime URL to SSM
- Frontend stack must have read access to SSM parameters
- Angular application must support async initialization

## Risks & Mitigations

**Risk**: Configuration fetch failure prevents app startup
**Mitigation**: Implement retry logic and fallback to environment.ts

**Risk**: Cached config.json serves stale URLs after infrastructure update
**Mitigation**: Set short cache TTL (5 minutes) and implement cache busting

**Risk**: Local development becomes more complex
**Mitigation**: Provide clear documentation and fallback mechanism

**Risk**: Breaking change for existing deployments
**Mitigation**: Implement backward compatibility, phased rollout

## Open Questions

1. Should config.json include additional values (feature flags, API keys)?
2. What cache TTL is appropriate for config.json? (Recommend: 5 minutes)
3. Should we support environment-specific config overrides?
4. How do we handle configuration during blue/green deployments?

## Next Steps

1. Create design document with detailed implementation plan
2. Update CDK stacks to export required values to SSM
3. Implement ConfigService in Angular application
4. Update frontend stack to generate and deploy config.json
5. Update GitHub Actions workflows to remove manual configuration
6. Test deployment pipeline end-to-end
7. Document local development setup

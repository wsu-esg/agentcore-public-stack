# Design Document: Environment-Agnostic Refactoring

## Overview

This design describes the refactoring of the AgentCore Public Stack from an environment-aware architecture to a fully configuration-driven, environment-agnostic system. The refactoring eliminates hardcoded environment logic (dev/test/prod conditionals) throughout the codebase and replaces it with explicit configuration parameters that can be set externally.

The design maintains backward compatibility during migration and supports both single-environment deployments (typical for open-source users) and multi-environment deployments (for the internal development team using GitHub Environments).

## Architecture

### Current Architecture (Environment-Aware)

```
┌─────────────────────────────────────────────────────────────┐
│ CDK Configuration (config.ts)                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ environment: 'prod' | 'dev' | 'test'                    │ │
│ │                                                         │ │
│ │ getResourceName(config, 'vpc')                          │ │
│ │   → if environment === 'prod': "prefix-vpc"             │ │
│ │   → else: "prefix-{env}-vpc"                            │ │
│ │                                                         │ │
│ │ removalPolicy: environment === 'prod' ? RETAIN : DESTROY│ │
│ │ corsOrigins: environment === 'prod' ? [...] : [...]     │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Deployment Scripts                                          │
│ DEPLOY_ENVIRONMENT=prod → cdk deploy --context env=prod     │
└─────────────────────────────────────────────────────────────┘
```

**Problems:**
- Code makes decisions based on environment names
- Users cannot control behavior without modifying code
- Environment logic scattered across ~15 locations
- Implicit behavior based on environment string

### Target Architecture (Configuration-Driven)

```
┌─────────────────────────────────────────────────────────────┐
│ External Configuration (GitHub Variables / Env Vars)        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ CDK_PROJECT_PREFIX: "myproject-prod"                    │ │
│ │ CDK_RETAIN_DATA_ON_DELETE: "true"                       │ │
│ │ CDK_FILE_UPLOAD_CORS_ORIGINS: "https://app.example.com" │ │
│ │ CDK_AWS_ACCOUNT: "123456789012"                         │ │
│ │ CDK_AWS_REGION: "us-west-2"                             │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ CDK Configuration (config.ts)                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ projectPrefix: string                                   │ │
│ │ retainDataOnDelete: boolean                             │ │
│ │ fileUpload.corsOrigins: string                          │ │
│ │                                                         │ │
│ │ getResourceName(config, 'vpc')                          │ │
│ │   → "{projectPrefix}-vpc"                               │ │
│ │                                                         │ │
│ │ removalPolicy: retainDataOnDelete ? RETAIN : DESTROY    │ │
│ │ corsOrigins: config.fileUpload.corsOrigins.split(',')   │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Deployment Scripts                                          │
│ cdk deploy (reads from environment variables)               │
└─────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Code has zero knowledge of environments
- All behavior controlled by explicit configuration
- Users have full control without code changes
- Configuration is visible and documented

## Components and Interfaces

### 1. CDK Configuration Module (`infrastructure/lib/config.ts`)

#### Current Interface

```typescript
export interface AppConfig {
  environment: 'prod' | 'dev' | 'test';  // ❌ Remove this
  projectPrefix: string;
  awsAccount: string;
  awsRegion: string;
  // ... other fields
}

export function getResourceName(config: AppConfig, ...parts: string[]): string {
  const envSuffix = config.environment === 'prod' ? '' : `-${config.environment}`;
  return [config.projectPrefix + envSuffix, ...parts].join('-');
}
```

#### New Interface

```typescript
export interface AppConfig {
  // Core identification
  projectPrefix: string;
  awsAccount: string;
  awsRegion: string;
  
  // Behavior flags
  retainDataOnDelete: boolean;  // ✅ New: Controls removal policies
  
  // Feature configuration
  fileUpload: {
    corsOrigins: string;  // Comma-separated list
    maxFileSizeMb: number;
  };
  
  appApi: {
    desiredCount: number;
    maxCapacity: number;
    cpu: number;
    memory: number;
  };
  
  inferenceApi: {
    desiredCount: number;
    maxCapacity: number;
    cpu: number;
    memory: number;
  };
  
  // Optional features
  enableAuthentication: boolean;
}

export function getResourceName(config: AppConfig, ...parts: string[]): string {
  // Simple concatenation - no environment logic
  return [config.projectPrefix, ...parts].join('-');
}

export function parseBooleanEnv(value: string | undefined, defaultValue: boolean = false): boolean {
  if (value === undefined) return defaultValue;
  return value.toLowerCase() === 'true' || value === '1';
}

export function loadConfig(scope: Construct): AppConfig {
  // Load from environment variables
  const projectPrefix = process.env.CDK_PROJECT_PREFIX;
  const awsAccount = process.env.CDK_AWS_ACCOUNT;
  const awsRegion = process.env.CDK_AWS_REGION;
  
  // Validate required fields
  if (!projectPrefix) throw new Error('CDK_PROJECT_PREFIX is required');
  if (!awsAccount) throw new Error('CDK_AWS_ACCOUNT is required');
  if (!awsRegion) throw new Error('CDK_AWS_REGION is required');
  
  // Load behavior flags with defaults
  const retainDataOnDelete = parseBooleanEnv(
    process.env.CDK_RETAIN_DATA_ON_DELETE,
    true  // Default to retaining data for safety
  );
  
  // Load feature configuration
  const corsOrigins = process.env.CDK_FILE_UPLOAD_CORS_ORIGINS || 'http://localhost:4200';
  
  const config: AppConfig = {
    projectPrefix,
    awsAccount,
    awsRegion,
    retainDataOnDelete,
    fileUpload: {
      corsOrigins,
      maxFileSizeMb: parseInt(process.env.CDK_FILE_UPLOAD_MAX_SIZE_MB || '10'),
    },
    appApi: {
      desiredCount: parseInt(process.env.CDK_APP_API_DESIRED_COUNT || '2'),
      maxCapacity: parseInt(process.env.CDK_APP_API_MAX_CAPACITY || '10'),
      cpu: parseInt(process.env.CDK_APP_API_CPU || '1024'),
      memory: parseInt(process.env.CDK_APP_API_MEMORY || '2048'),
    },
    inferenceApi: {
      desiredCount: parseInt(process.env.CDK_INFERENCE_API_DESIRED_COUNT || '2'),
      maxCapacity: parseInt(process.env.CDK_INFERENCE_API_MAX_CAPACITY || '10'),
      cpu: parseInt(process.env.CDK_INFERENCE_API_CPU || '1024'),
      memory: parseInt(process.env.CDK_INFERENCE_API_MEMORY || '2048'),
    },
    enableAuthentication: parseBooleanEnv(
      process.env.CDK_ENABLE_AUTHENTICATION,
      true
    ),
  };
  
  // Log configuration for debugging
  console.log('📋 Loaded CDK Configuration:');
  console.log(`   Project Prefix: ${config.projectPrefix}`);
  console.log(`   AWS Account: ${config.awsAccount}`);
  console.log(`   AWS Region: ${config.awsRegion}`);
  console.log(`   Retain Data on Delete: ${config.retainDataOnDelete}`);
  console.log(`   CORS Origins: ${config.fileUpload.corsOrigins}`);
  
  return config;
}
```

### 2. Removal Policy Helper

```typescript
export function getRemovalPolicy(config: AppConfig): cdk.RemovalPolicy {
  return config.retainDataOnDelete 
    ? cdk.RemovalPolicy.RETAIN 
    : cdk.RemovalPolicy.DESTROY;
}

export function getAutoDeleteObjects(config: AppConfig): boolean {
  return !config.retainDataOnDelete;
}
```

### 3. Stack Updates

#### DynamoDB Tables (15 instances across stacks)

**Before:**
```typescript
const userQuotaTable = new dynamodb.Table(this, 'UserQuotaTable', {
  tableName: getResourceName(config, 'user-quotas'),
  removalPolicy: config.environment === 'prod' 
    ? cdk.RemovalPolicy.RETAIN 
    : cdk.RemovalPolicy.DESTROY,
  // ...
});
```

**After:**
```typescript
const userQuotaTable = new dynamodb.Table(this, 'UserQuotaTable', {
  tableName: getResourceName(config, 'user-quotas'),
  removalPolicy: getRemovalPolicy(config),
  // ...
});
```

#### S3 Buckets

**Before:**
```typescript
const userFilesBucket = new s3.Bucket(this, 'UserFilesBucket', {
  bucketName: getResourceName(config, 'user-files'),
  removalPolicy: config.environment === 'prod' 
    ? cdk.RemovalPolicy.RETAIN 
    : cdk.RemovalPolicy.DESTROY,
  autoDeleteObjects: config.environment !== 'prod',
  // ...
});
```

**After:**
```typescript
const userFilesBucket = new s3.Bucket(this, 'UserFilesBucket', {
  bucketName: getResourceName(config, 'user-files'),
  removalPolicy: getRemovalPolicy(config),
  autoDeleteObjects: getAutoDeleteObjects(config),
  // ...
});
```

#### CORS Configuration

**Before:**
```typescript
const fileUploadCorsOrigins = config.fileUpload?.corsOrigins
  ? config.fileUpload.corsOrigins.split(",").map((o) => o.trim())
  : config.environment === "prod"
    ? ["https://boisestate.ai", "https://*.boisestate.ai"]
    : ["http://localhost:4200", "http://localhost:8000"];
```

**After:**
```typescript
const fileUploadCorsOrigins = config.fileUpload.corsOrigins
  .split(",")
  .map((o) => o.trim());
```

### 4. Deployment Scripts

#### `scripts/common/load-env.sh`

**Before:**
```bash
#!/bin/bash
export DEPLOY_ENVIRONMENT="${DEPLOY_ENVIRONMENT:-prod}"
export CDK_PROJECT_PREFIX="${CDK_PROJECT_PREFIX}"
export CDK_AWS_ACCOUNT="${CDK_AWS_ACCOUNT}"
export CDK_AWS_REGION="${CDK_AWS_REGION}"
```

**After:**
```bash
#!/bin/bash
# Load configuration from environment variables
# All CDK_* variables should be set in GitHub Environment or .env file

# Required variables
: "${CDK_PROJECT_PREFIX:?CDK_PROJECT_PREFIX is required}"
: "${CDK_AWS_ACCOUNT:?CDK_AWS_ACCOUNT is required}"
: "${CDK_AWS_REGION:?CDK_AWS_REGION is required}"

# Optional variables with defaults
export CDK_RETAIN_DATA_ON_DELETE="${CDK_RETAIN_DATA_ON_DELETE:-true}"
export CDK_FILE_UPLOAD_CORS_ORIGINS="${CDK_FILE_UPLOAD_CORS_ORIGINS:-http://localhost:4200}"
export CDK_ENABLE_AUTHENTICATION="${CDK_ENABLE_AUTHENTICATION:-true}"

echo "📋 Configuration loaded:"
echo "   Project Prefix: ${CDK_PROJECT_PREFIX}"
echo "   AWS Region: ${CDK_AWS_REGION}"
echo "   Retain Data: ${CDK_RETAIN_DATA_ON_DELETE}"
```

#### CDK Deployment Commands

**Before:**
```bash
cdk synth InfrastructureStack \
    --context environment="${DEPLOY_ENVIRONMENT}" \
    --context projectPrefix="${CDK_PROJECT_PREFIX}" \
    # ...
```

**After:**
```bash
# No context parameters needed - config loaded from environment variables
cdk synth InfrastructureStack
```

### 5. Frontend Configuration

#### Current Approach (Multiple Files)

```
src/environments/
├── environment.ts              # Default (localhost)
├── environment.development.ts  # Dev (hardcoded URLs)
└── environment.production.ts   # Prod (hardcoded URLs)
```

#### New Approach (Single Template + Injection)

```
src/environments/
└── environment.ts              # Single file with placeholders
```

**environment.ts (template):**
```typescript
export const environment = {
  production: ${PRODUCTION},
  appApiUrl: '${APP_API_URL}',
  inferenceApiUrl: '${INFERENCE_API_URL}',
  enableAuthentication: ${ENABLE_AUTHENTICATION}
};
```

**Build script (`scripts/stack-frontend/build.sh`):**
```bash
#!/bin/bash

# Default values for local development
export PRODUCTION="${PRODUCTION:-false}"
export APP_API_URL="${APP_API_URL:-http://localhost:8000}"
export INFERENCE_API_URL="${INFERENCE_API_URL:-http://localhost:8001}"
export ENABLE_AUTHENTICATION="${ENABLE_AUTHENTICATION:-true}"

# Substitute environment variables
envsubst < src/environments/environment.ts.template > src/environments/environment.ts

# Build Angular app
ng build --configuration production
```

### 6. GitHub Environments Configuration

#### Environment Structure

```
GitHub Repository Settings → Environments
├── development
│   ├── Variables:
│   │   ├── CDK_PROJECT_PREFIX: "agentcore-dev"
│   │   ├── CDK_AWS_REGION: "us-west-2"
│   │   ├── CDK_RETAIN_DATA_ON_DELETE: "false"
│   │   ├── CDK_APP_API_DESIRED_COUNT: "1"
│   │   ├── CDK_FILE_UPLOAD_CORS_ORIGINS: "http://localhost:4200,https://dev.example.com"
│   │   ├── APP_API_URL: "https://dev-api.example.com"
│   │   └── INFERENCE_API_URL: "https://dev-inference.example.com"
│   └── Secrets:
│       ├── AWS_ROLE_ARN: "arn:aws:iam::111111111111:role/dev-deploy"
│       └── CDK_AWS_ACCOUNT: "111111111111"
│
├── staging
│   ├── Variables: (similar structure with staging values)
│   └── Secrets: (staging AWS account)
│
└── production
    ├── Variables:
    │   ├── CDK_PROJECT_PREFIX: "agentcore-prod"
    │   ├── CDK_RETAIN_DATA_ON_DELETE: "true"
    │   ├── CDK_APP_API_DESIRED_COUNT: "3"
    │   └── ... (production values)
    ├── Secrets: (production AWS account)
    └── Protection Rules:
        ├── Required reviewers: 2
        └── Wait timer: 5 minutes
```

#### Workflow Updates

**`.github/workflows/infrastructure.yml`:**

```yaml
name: Deploy Infrastructure

on:
  push:
    branches: [main, develop]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        type: choice
        options: [development, staging, production]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    # Select environment based on trigger
    environment: ${{ 
      github.event.inputs.environment || 
      (github.ref == 'refs/heads/main' && 'production' || 'development') 
    }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ vars.CDK_AWS_REGION }}
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: |
          cd infrastructure
          npm install
      
      - name: Deploy Infrastructure
        run: |
          cd infrastructure
          npx cdk deploy InfrastructureStack --require-approval never
        env:
          # All configuration comes from GitHub Environment
          CDK_PROJECT_PREFIX: ${{ vars.CDK_PROJECT_PREFIX }}
          CDK_AWS_ACCOUNT: ${{ secrets.CDK_AWS_ACCOUNT }}
          CDK_AWS_REGION: ${{ vars.CDK_AWS_REGION }}
          CDK_RETAIN_DATA_ON_DELETE: ${{ vars.CDK_RETAIN_DATA_ON_DELETE }}
          CDK_FILE_UPLOAD_CORS_ORIGINS: ${{ vars.CDK_FILE_UPLOAD_CORS_ORIGINS }}
          CDK_APP_API_DESIRED_COUNT: ${{ vars.CDK_APP_API_DESIRED_COUNT }}
          CDK_APP_API_MAX_CAPACITY: ${{ vars.CDK_APP_API_MAX_CAPACITY }}
```

## Data Models

### Configuration Schema

```typescript
interface AppConfig {
  // Identity
  projectPrefix: string;          // e.g., "agentcore-prod", "mycompany-dev"
  awsAccount: string;             // 12-digit AWS account ID
  awsRegion: string;              // AWS region code
  
  // Behavior
  retainDataOnDelete: boolean;    // true = RETAIN, false = DESTROY
  
  // Features
  fileUpload: {
    corsOrigins: string;          // Comma-separated URLs
    maxFileSizeMb: number;        // Max file size in MB
  };
  
  appApi: {
    desiredCount: number;         // ECS task count
    maxCapacity: number;          // Auto-scaling max
    cpu: number;                  // CPU units (1024 = 1 vCPU)
    memory: number;               // Memory in MB
  };
  
  inferenceApi: {
    desiredCount: number;
    maxCapacity: number;
    cpu: number;
    memory: number;
  };
  
  enableAuthentication: boolean;  // Enable/disable auth
  
  // Deprecated
  environment?: string;           // For backward compatibility
}
```

### Environment Variable Mapping

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `CDK_PROJECT_PREFIX` | string | (required) | Resource name prefix |
| `CDK_AWS_ACCOUNT` | string | (required) | AWS account ID |
| `CDK_AWS_REGION` | string | (required) | AWS region |
| `CDK_RETAIN_DATA_ON_DELETE` | boolean | `true` | Retain data on stack deletion |
| `CDK_FILE_UPLOAD_CORS_ORIGINS` | string | `http://localhost:4200` | Allowed CORS origins |
| `CDK_FILE_UPLOAD_MAX_SIZE_MB` | number | `10` | Max file upload size |
| `CDK_APP_API_DESIRED_COUNT` | number | `2` | App API task count |
| `CDK_APP_API_MAX_CAPACITY` | number | `10` | App API max tasks |
| `CDK_APP_API_CPU` | number | `1024` | App API CPU units |
| `CDK_APP_API_MEMORY` | number | `2048` | App API memory MB |
| `CDK_INFERENCE_API_DESIRED_COUNT` | number | `2` | Inference API task count |
| `CDK_INFERENCE_API_MAX_CAPACITY` | number | `10` | Inference API max tasks |
| `CDK_INFERENCE_API_CPU` | number | `1024` | Inference API CPU units |
| `CDK_INFERENCE_API_MEMORY` | number | `2048` | Inference API memory MB |
| `CDK_ENABLE_AUTHENTICATION` | boolean | `true` | Enable authentication |
| `APP_API_URL` | string | `http://localhost:8000` | Frontend: App API URL |
| `INFERENCE_API_URL` | string | `http://localhost:8001` | Frontend: Inference API URL |
| `PRODUCTION` | boolean | `false` | Frontend: Production mode |
| `ENABLE_AUTHENTICATION` | boolean | `true` | Frontend: Enable auth |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Prework Analysis Summary

After analyzing all acceptance criteria, the following are testable as properties or examples:

**Properties (universal rules):**
- Resource naming behavior (2.1-2.3)
- Removal policy mapping (3.2-3.3)
- CORS configuration loading (4.1, 4.4)
- Environment variable substitution (6.1, 6.3)
- Configuration loading from CDK_* variables (7.1, 7.3, 7.4)
- Validation behavior (11.1-11.5)
- Frontend runtime validation (14.5)

**Examples (specific cases):**
- Interface structure checks (1.1, 1.4, 3.1, 6.2, 6.4, 7.2, 14.1)
- Static analysis checks (1.1, 3.4, 4.3, 5.1, 5.2, 5.4, 6.5, 10.1-10.6, 13.1)
- Default value checks (4.2)

**Not testable:**
- Documentation requirements (8.*, 12.*)
- GitHub Actions workflow configuration (9.*)
- Logging behavior (7.5)
- Script execution behavior (5.3, 13.2, 13.4, 13.5, 14.4)

### Property 1: Resource Naming is Environment-Agnostic

*For any* project prefix and resource name parts, the generated resource name should be the project prefix concatenated with the resource parts using hyphens, with no automatic environment suffixes (`-dev`, `-test`, `-prod`) added.

**Validates: Requirements 2.1, 2.2, 2.3**

### Property 2: Removal Policy Follows Retention Flag

*For any* configuration with a `retainDataOnDelete` flag, when the flag is true, data resources (DynamoDB tables, S3 buckets) should have removal policy RETAIN, and when the flag is false, they should have removal policy DESTROY with `autoDeleteObjects` enabled for S3 buckets.

**Validates: Requirements 3.2, 3.3**

### Property 3: CORS Origins are Configuration-Driven

*For any* CORS configuration value, the system should parse it as a comma-separated list and use those origins without hardcoded environment-specific defaults.

**Validates: Requirements 4.1, 4.4**

### Property 4: Environment Variable Substitution Works Correctly

*For any* template file with placeholder variables and corresponding environment variables, the build process should replace all placeholders with the environment variable values.

**Validates: Requirements 6.1, 6.3**

### Property 5: Configuration Loads from CDK_* Variables

*For any* environment variable with `CDK_` prefix, the configuration loader should read and use that value, and when a variable is not set, it should use the documented default value.

**Validates: Requirements 7.1, 7.3**

### Property 6: Required Configuration Validation

*For any* missing required configuration variable (projectPrefix, awsAccount, awsRegion), the system should throw an error before deployment that includes the variable name in the error message.

**Validates: Requirements 7.4, 11.1, 11.2**

### Property 7: Configuration Value Validation

*For any* configuration value that has format requirements (boolean flags, AWS account IDs, AWS regions), the system should validate the format and reject invalid values with descriptive errors.

**Validates: Requirements 11.3, 11.4, 11.5**

### Property 8: Frontend Runtime Validation

*For any* required frontend configuration value (appApiUrl, inferenceApiUrl), when the value is missing or invalid at runtime, the frontend should detect and report the configuration error.

**Validates: Requirements 14.5**

### Property 9: No Environment Conditionals in Codebase

*For all* CDK stack files (infrastructure-stack.ts, app-api-stack.ts, inference-api-stack.ts, frontend-stack.ts, gateway-stack.ts), the code should contain zero references to `config.environment` property or `environment === 'prod'` conditionals.

**Validates: Requirements 3.4, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**

## Error Handling

### Configuration Loading Errors

**Missing Required Variables:**
```typescript
if (!projectPrefix) {
  throw new Error(
    'CDK_PROJECT_PREFIX is required. ' +
    'Set this environment variable to your desired resource name prefix ' +
    '(e.g., "mycompany-agentcore" or "mycompany-agentcore-prod")'
  );
}
```

**Invalid Boolean Values:**
```typescript
function parseBooleanEnv(value: string | undefined, defaultValue: boolean): boolean {
  if (value === undefined) return defaultValue;
  
  const normalized = value.toLowerCase();
  if (normalized === 'true' || normalized === '1') return true;
  if (normalized === 'false' || normalized === '0') return false;
  
  throw new Error(
    `Invalid boolean value: "${value}". ` +
    `Expected "true", "false", "1", or "0".`
  );
}
```

**Invalid AWS Account ID:**
```typescript
function validateAwsAccount(account: string): void {
  if (!/^\d{12}$/.test(account)) {
    throw new Error(
      `Invalid AWS account ID: "${account}". ` +
      `Expected a 12-digit number.`
    );
  }
}
```

**Invalid AWS Region:**
```typescript
const VALID_REGIONS = [
  'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
  'eu-west-1', 'eu-west-2', 'eu-central-1',
  'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1',
  // ... other regions
];

function validateAwsRegion(region: string): void {
  if (!VALID_REGIONS.includes(region)) {
    throw new Error(
      `Invalid AWS region: "${region}". ` +
      `Expected one of: ${VALID_REGIONS.join(', ')}`
    );
  }
}
```

### Deployment Errors

**Resource Name Conflicts:**
When deploying multiple environments to the same AWS account, users must use different project prefixes to avoid resource name conflicts.

```
Error: Resource with name "agentcore-vpc" already exists
Solution: Use a different CDK_PROJECT_PREFIX value (e.g., "agentcore-dev" vs "agentcore-prod")
```

**CORS Configuration Errors:**
Invalid CORS origins will cause API Gateway or ALB to reject requests.

```typescript
function validateCorsOrigins(origins: string): void {
  const originList = origins.split(',').map(o => o.trim());
  
  for (const origin of originList) {
    try {
      new URL(origin);
    } catch (e) {
      throw new Error(
        `Invalid CORS origin: "${origin}". ` +
        `Expected a valid URL (e.g., "https://example.com")`
      );
    }
  }
}
```

### Frontend Build Errors

**Missing Environment Variables:**
```bash
#!/bin/bash
: "${APP_API_URL:?APP_API_URL is required for production builds}"
: "${INFERENCE_API_URL:?INFERENCE_API_URL is required for production builds}"
```

**Template Substitution Errors:**
```bash
if ! command -v envsubst &> /dev/null; then
  echo "Error: envsubst command not found"
  echo "Install gettext package: apt-get install gettext-base"
  exit 1
fi
```

### Migration Errors

**Configuration Not Found:**
```typescript
// No backward compatibility - users must migrate fully
if (process.env.DEPLOY_ENVIRONMENT) {
  throw new Error(
    '\n❌ DEPLOY_ENVIRONMENT is no longer supported\n' +
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
    `Please migrate to explicit configuration:\n\n` +
    `  Remove: DEPLOY_ENVIRONMENT=prod\n` +
    `  Add:    CDK_PROJECT_PREFIX=myproject-prod\n` +
    `          CDK_RETAIN_DATA_ON_DELETE=true\n\n` +
    `See migration guide: docs/MIGRATION_GUIDE.md\n` +
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
  );
}
```

## Testing Strategy

### Unit Tests

**Configuration Loading Tests:**
```typescript
describe('loadConfig', () => {
  it('should load configuration from environment variables', () => {
    process.env.CDK_PROJECT_PREFIX = 'test-project';
    process.env.CDK_AWS_ACCOUNT = '123456789012';
    process.env.CDK_AWS_REGION = 'us-west-2';
    
    const config = loadConfig(mockScope);
    
    expect(config.projectPrefix).toBe('test-project');
    expect(config.awsAccount).toBe('123456789012');
    expect(config.awsRegion).toBe('us-west-2');
  });
  
  it('should throw error when required variables are missing', () => {
    delete process.env.CDK_PROJECT_PREFIX;
    
    expect(() => loadConfig(mockScope)).toThrow('CDK_PROJECT_PREFIX is required');
  });
  
  it('should use default values for optional variables', () => {
    // Set only required variables
    process.env.CDK_PROJECT_PREFIX = 'test';
    process.env.CDK_AWS_ACCOUNT = '123456789012';
    process.env.CDK_AWS_REGION = 'us-west-2';
    
    const config = loadConfig(mockScope);
    
    expect(config.retainDataOnDelete).toBe(true);  // Default
    expect(config.fileUpload.corsOrigins).toBe('http://localhost:4200');  // Default
  });
});
```

**Resource Naming Tests:**
```typescript
describe('getResourceName', () => {
  it('should concatenate prefix and parts with hyphens', () => {
    const config = { projectPrefix: 'myproject' };
    
    expect(getResourceName(config, 'vpc')).toBe('myproject-vpc');
    expect(getResourceName(config, 'user', 'quotas')).toBe('myproject-user-quotas');
  });
  
  it('should not add environment suffixes', () => {
    const config = { projectPrefix: 'myproject' };
    
    const name = getResourceName(config, 'vpc');
    
    expect(name).not.toContain('-dev');
    expect(name).not.toContain('-test');
    expect(name).not.toContain('-prod');
  });
  
  it('should preserve environment in prefix if user includes it', () => {
    const config = { projectPrefix: 'myproject-dev' };
    
    expect(getResourceName(config, 'vpc')).toBe('myproject-dev-vpc');
  });
});
```

**Removal Policy Tests:**
```typescript
describe('getRemovalPolicy', () => {
  it('should return RETAIN when retainDataOnDelete is true', () => {
    const config = { retainDataOnDelete: true };
    
    expect(getRemovalPolicy(config)).toBe(cdk.RemovalPolicy.RETAIN);
  });
  
  it('should return DESTROY when retainDataOnDelete is false', () => {
    const config = { retainDataOnDelete: false };
    
    expect(getRemovalPolicy(config)).toBe(cdk.RemovalPolicy.DESTROY);
  });
});

describe('getAutoDeleteObjects', () => {
  it('should return false when retainDataOnDelete is true', () => {
    const config = { retainDataOnDelete: true };
    
    expect(getAutoDeleteObjects(config)).toBe(false);
  });
  
  it('should return true when retainDataOnDelete is false', () => {
    const config = { retainDataOnDelete: false };
    
    expect(getAutoDeleteObjects(config)).toBe(true);
  });
});
```

**Boolean Parsing Tests:**
```typescript
describe('parseBooleanEnv', () => {
  it('should parse "true" as true', () => {
    expect(parseBooleanEnv('true')).toBe(true);
    expect(parseBooleanEnv('TRUE')).toBe(true);
    expect(parseBooleanEnv('1')).toBe(true);
  });
  
  it('should parse "false" as false', () => {
    expect(parseBooleanEnv('false')).toBe(false);
    expect(parseBooleanEnv('FALSE')).toBe(false);
    expect(parseBooleanEnv('0')).toBe(false);
  });
  
  it('should use default value when undefined', () => {
    expect(parseBooleanEnv(undefined, true)).toBe(true);
    expect(parseBooleanEnv(undefined, false)).toBe(false);
  });
  
  it('should throw error for invalid values', () => {
    expect(() => parseBooleanEnv('yes')).toThrow('Invalid boolean value');
    expect(() => parseBooleanEnv('no')).toThrow('Invalid boolean value');
    expect(() => parseBooleanEnv('maybe')).toThrow('Invalid boolean value');
  });
});
```

**Validation Tests:**
```typescript
describe('validateAwsAccount', () => {
  it('should accept valid 12-digit account IDs', () => {
    expect(() => validateAwsAccount('123456789012')).not.toThrow();
  });
  
  it('should reject non-12-digit account IDs', () => {
    expect(() => validateAwsAccount('12345')).toThrow('Invalid AWS account ID');
    expect(() => validateAwsAccount('12345678901234')).toThrow('Invalid AWS account ID');
  });
  
  it('should reject non-numeric account IDs', () => {
    expect(() => validateAwsAccount('abcdefghijkl')).toThrow('Invalid AWS account ID');
  });
});

describe('validateAwsRegion', () => {
  it('should accept valid AWS regions', () => {
    expect(() => validateAwsRegion('us-east-1')).not.toThrow();
    expect(() => validateAwsRegion('eu-west-1')).not.toThrow();
  });
  
  it('should reject invalid regions', () => {
    expect(() => validateAwsRegion('invalid-region')).toThrow('Invalid AWS region');
    expect(() => validateAwsRegion('us-east-99')).toThrow('Invalid AWS region');
  });
});
```

### Property-Based Tests

**Property Test 1: Resource Naming (Property 1)**
```typescript
import * as fc from 'fast-check';

describe('Property: Resource naming is environment-agnostic', () => {
  it('should never add environment suffixes to resource names', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 20 }).filter(s => /^[a-z0-9-]+$/.test(s)),
        fc.array(fc.string({ minLength: 1, maxLength: 10 }).filter(s => /^[a-z0-9-]+$/.test(s))),
        (prefix, parts) => {
          const config = { projectPrefix: prefix };
          const name = getResourceName(config, ...parts);
          
          // Should not contain environment suffixes
          const hasEnvSuffix = name.endsWith('-dev') || 
                               name.endsWith('-test') || 
                               name.endsWith('-prod');
          
          return !hasEnvSuffix;
        }
      ),
      { numRuns: 100 }
    );
  });
});

// Feature: environment-agnostic-refactor, Property 1: Resource naming is environment-agnostic
```

**Property Test 2: Removal Policy Mapping (Property 2)**
```typescript
describe('Property: Removal policy follows retention flag', () => {
  it('should map retainDataOnDelete to correct removal policies', () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        (retainDataOnDelete) => {
          const config = { retainDataOnDelete };
          
          const removalPolicy = getRemovalPolicy(config);
          const autoDelete = getAutoDeleteObjects(config);
          
          if (retainDataOnDelete) {
            return removalPolicy === cdk.RemovalPolicy.RETAIN && autoDelete === false;
          } else {
            return removalPolicy === cdk.RemovalPolicy.DESTROY && autoDelete === true;
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

// Feature: environment-agnostic-refactor, Property 2: Removal policy follows retention flag
```

**Property Test 3: CORS Configuration (Property 3)**
```typescript
describe('Property: CORS origins are configuration-driven', () => {
  it('should parse comma-separated CORS origins correctly', () => {
    fc.assert(
      fc.property(
        fc.array(fc.webUrl(), { minLength: 1, maxLength: 5 }),
        (urls) => {
          const corsString = urls.join(',');
          const config = { fileUpload: { corsOrigins: corsString } };
          
          const parsed = config.fileUpload.corsOrigins.split(',').map(o => o.trim());
          
          return parsed.length === urls.length && 
                 parsed.every((url, i) => url === urls[i]);
        }
      ),
      { numRuns: 100 }
    );
  });
});

// Feature: environment-agnostic-refactor, Property 3: CORS origins are configuration-driven
```

**Property Test 4: Configuration Loading (Property 5)**
```typescript
describe('Property: Configuration loads from CDK_* variables', () => {
  it('should load all CDK_* environment variables correctly', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 20 }),
        fc.string({ minLength: 12, maxLength: 12 }).filter(s => /^\d+$/.test(s)),
        fc.constantFrom('us-east-1', 'us-west-2', 'eu-west-1'),
        (prefix, account, region) => {
          process.env.CDK_PROJECT_PREFIX = prefix;
          process.env.CDK_AWS_ACCOUNT = account;
          process.env.CDK_AWS_REGION = region;
          
          const config = loadConfig(mockScope);
          
          return config.projectPrefix === prefix &&
                 config.awsAccount === account &&
                 config.awsRegion === region;
        }
      ),
      { numRuns: 100 }
    );
  });
});

// Feature: environment-agnostic-refactor, Property 5: Configuration loads from CDK_* variables
```

**Property Test 5: Validation (Property 7)**
```typescript
describe('Property: Configuration value validation', () => {
  it('should reject invalid AWS account IDs', () => {
    fc.assert(
      fc.property(
        fc.string().filter(s => !/^\d{12}$/.test(s)),
        (invalidAccount) => {
          try {
            validateAwsAccount(invalidAccount);
            return false;  // Should have thrown
          } catch (e) {
            return e.message.includes('Invalid AWS account ID');
          }
        }
      ),
      { numRuns: 100 }
    );
  });
  
  it('should reject invalid boolean strings', () => {
    fc.assert(
      fc.property(
        fc.string().filter(s => !['true', 'false', '1', '0', 'TRUE', 'FALSE'].includes(s)),
        (invalidBool) => {
          try {
            parseBooleanEnv(invalidBool);
            return false;  // Should have thrown
          } catch (e) {
            return e.message.includes('Invalid boolean value');
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

// Feature: environment-agnostic-refactor, Property 7: Configuration value validation
```

### Integration Tests

**CDK Synthesis Test:**
```typescript
describe('CDK Stack Synthesis', () => {
  it('should synthesize stacks without environment parameter', () => {
    const app = new cdk.App();
    
    process.env.CDK_PROJECT_PREFIX = 'test-project';
    process.env.CDK_AWS_ACCOUNT = '123456789012';
    process.env.CDK_AWS_REGION = 'us-west-2';
    process.env.CDK_RETAIN_DATA_ON_DELETE = 'false';
    
    const stack = new InfrastructureStack(app, 'TestStack');
    const template = Template.fromStack(stack);
    
    // Verify resources are created with correct names
    template.hasResourceProperties('AWS::EC2::VPC', {
      Tags: [{ Key: 'Name', Value: 'test-project-vpc' }]
    });
    
    // Verify no environment-based logic
    const resources = template.toJSON().Resources;
    const resourceNames = Object.values(resources).map((r: any) => r.Properties?.TableName || r.Properties?.BucketName);
    
    resourceNames.forEach(name => {
      if (name) {
        expect(name).not.toContain('-dev');
        expect(name).not.toContain('-test');
        expect(name).not.toContain('-prod');
      }
    });
  });
});
```

**Frontend Build Test:**
```bash
#!/bin/bash
# Test frontend build with environment variable substitution

export APP_API_URL="https://test-api.example.com"
export INFERENCE_API_URL="https://test-inference.example.com"
export PRODUCTION="true"
export ENABLE_AUTHENTICATION="true"

# Run build
cd frontend/ai.client
npm run build

# Verify substitution worked
if grep -q "https://test-api.example.com" dist/*/main.*.js; then
  echo "✅ Environment variable substitution successful"
else
  echo "❌ Environment variable substitution failed"
  exit 1
fi
```

### Static Analysis Tests

**Grep Tests for Environment References:**
```bash
#!/bin/bash
# Test that no environment conditionals exist in CDK code

echo "Checking for environment conditionals..."

# Check for config.environment references
if grep -r "config\.environment" infrastructure/lib/*.ts; then
  echo "❌ Found config.environment references"
  exit 1
fi

# Check for DEPLOY_ENVIRONMENT references
if grep -r "DEPLOY_ENVIRONMENT" scripts/; then
  echo "❌ Found DEPLOY_ENVIRONMENT references"
  exit 1
fi

# Check for environment === 'prod' patterns
if grep -r "environment === ['\"]prod['\"]" infrastructure/lib/*.ts; then
  echo "❌ Found environment === 'prod' conditionals"
  exit 1
fi

echo "✅ No environment conditionals found"
```

### Test Coverage Goals

- **Unit tests**: 90%+ coverage of configuration loading and helper functions
- **Property tests**: 100 iterations minimum per property
- **Integration tests**: All CDK stacks synthesize successfully
- **Static analysis**: Zero environment conditionals in production code
- **End-to-end**: Successful deployment to test environment with new configuration

### Testing During Migration

**Migration Testing:**
- Test all stacks with new configuration variables only
- Verify resource names match expectations
- Confirm removal policies are correct
- Ensure DEPLOY_ENVIRONMENT throws clear error if present
- Verify all environment conditionals are removed

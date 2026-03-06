# Runtime Configuration Feature - Design Document

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Deployment Time                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  InfrastructureStack          AppApiStack                        │
│         │                          │                             │
│         ├─ ALB URL ────────────────┼─> SSM Parameter             │
│         │                          │   /project/network/alb-url  │
│         │                          │                             │
│  InferenceApiStack                 │                             │
│         │                          │                             │
│         ├─ Runtime ARN ────────────┼─> SSM Parameter             │
│                                    │   /project/inference-api/   │
│                                    │   runtime-endpoint-url      │
│                                    │                             │
│                                    ▼                             │
│                          FrontendStack                           │
│                                    │                             │
│                    ┌───────────────┴───────────────┐            │
│                    │                                 │            │
│                    ▼                                 ▼            │
│            Read SSM Parameters          Generate config.json     │
│                                                     │            │
│                                                     ▼            │
│                                         Deploy to S3 + CloudFront│
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Runtime (Browser)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. User navigates to app                                        │
│         │                                                         │
│         ▼                                                         │
│  2. Angular bootstrap starts                                     │
│         │                                                         │
│         ▼                                                         │
│  3. APP_INITIALIZER runs                                         │
│         │                                                         │
│         ├─> Fetch /config.json from CloudFront                   │
│         │                                                         │
│         ├─> Parse and validate configuration                     │
│         │                                                         │
│         ├─> Store in ConfigService                               │
│         │                                                         │
│         ▼                                                         │
│  4. App initialization completes                                 │
│         │                                                         │
│         ▼                                                         │
│  5. Services use ConfigService.get('appApiUrl')                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Design

### 0. New Configuration Property: Production Flag

Following the configuration flow pattern from devops.md, we need to add a `production` boolean property:

#### Step 1: Add to TypeScript Config Interface
**File**: `infrastructure/lib/config.ts`

```typescript
export interface AppConfig {
  projectPrefix: string;
  awsAccount: string;
  awsRegion: string;
  production: boolean;  // NEW: Production environment flag
  // ... other properties
}
```

#### Step 2: Load from Environment/Context
**File**: `infrastructure/lib/config.ts` (in `loadConfig` function)

```typescript
const config: AppConfig = {
  projectPrefix,
  awsAccount,
  awsRegion,
  production: parseBooleanEnv(process.env.CDK_PRODUCTION, true), // Default: true
  // ... other properties
};
```

**Note**: Default value is `true` (production mode). This is the safe default - non-production environments must explicitly set `CDK_PRODUCTION=false`.

#### Step 3: Add to load-env.sh
**File**: `scripts/common/load-env.sh`

```bash
# Export the variable (priority: env var > context file)
export CDK_PRODUCTION="${CDK_PRODUCTION:-$(get_json_value "production" "${CONTEXT_FILE}")}"

# Add to context parameters function (optional parameter)
if [ -n "${CDK_PRODUCTION:-}" ]; then
    context_params="${context_params} --context production=\"${CDK_PRODUCTION}\""
fi

# Display in config output
log_info "  Production:     ${CDK_PRODUCTION:-true}"
```

#### Step 4: Update Stack Scripts
**Files**: `scripts/stack-frontend/synth.sh` and `scripts/stack-frontend/deploy.sh`

```bash
# Both scripts must have identical context parameters
cdk synth FrontendStack \
    --context production="${CDK_PRODUCTION}" \
    # ... other context params
```

#### Step 5: Add to GitHub Workflow
**File**: `.github/workflows/frontend.yml`

```yaml
env:
  # CDK Configuration - from GitHub Variables
  CDK_PRODUCTION: ${{ vars.CDK_PRODUCTION }}  # "true" or "false"
```

#### Step 6: Set in GitHub Repository
**Settings → Secrets and variables → Actions → Variables**:
- For production: `CDK_PRODUCTION = true`
- For dev/staging: `CDK_PRODUCTION = false`

**Rationale**: This is a non-sensitive configuration value, so it goes in Variables (not Secrets).

### 1. Infrastructure Changes

#### 1.1 InfrastructureStack - Export ALB URL to SSM

**Current State**: ALB URL is output to CloudFormation only

**New State**: ALB URL is stored in SSM parameter

```typescript
// infrastructure/lib/infrastructure-stack.ts

// After ALB creation, store URL in SSM
new ssm.StringParameter(this, 'AlbUrlParameter', {
  parameterName: `/${config.projectPrefix}/network/alb-url`,
  stringValue: config.certificateArn 
    ? `https://${albRecordName}`
    : `http://${albRecordName}`,
  description: 'Application Load Balancer URL',
  tier: ssm.ParameterTier.STANDARD,
});
```

**Rationale**: Frontend stack needs to read this value at synth time

#### 1.2 InferenceApiStack - Export Runtime Endpoint URL to SSM

**Current State**: Runtime ARN is stored in SSM, but not the full endpoint URL

**New State**: Full endpoint URL is stored in SSM parameter

```typescript
// infrastructure/lib/inference-api-stack.ts

// Construct the full endpoint URL
const runtimeEndpointUrl = cdk.Fn.sub(
  'https://bedrock-agentcore.${AWS::Region}.amazonaws.com/runtimes/${RuntimeArn}',
  { RuntimeArn: this.runtime.attrAgentRuntimeArn }
);

new ssm.StringParameter(this, 'InferenceApiRuntimeEndpointUrlParameter', {
  parameterName: `/${config.projectPrefix}/inference-api/runtime-endpoint-url`,
  stringValue: runtimeEndpointUrl,
  description: 'Inference API AgentCore Runtime Endpoint URL',
  tier: ssm.ParameterTier.STANDARD,
});
```

**Note**: ARN will need to be URL-encoded by the consuming application when making requests

#### 1.3 FrontendStack - Generate and Deploy config.json

**Current State**: Frontend stack deploys static assets only

**New State**: Frontend stack generates config.json and deploys it

```typescript
// infrastructure/lib/frontend-stack.ts

import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';

// Read backend URLs from SSM
const appApiUrl = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/network/alb-url`
);

const inferenceApiUrl = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/inference-api/runtime-endpoint-url`
);

// Generate config.json content
const runtimeConfig = {
  appApiUrl: appApiUrl,
  inferenceApiUrl: inferenceApiUrl,
  enableAuthentication: true,
  environment: config.production ? 'production' : 'development',
};

// Deploy config.json alongside static assets
new s3deploy.BucketDeployment(this, 'RuntimeConfigDeployment', {
  sources: [
    s3deploy.Source.jsonData('config.json', runtimeConfig),
  ],
  destinationBucket: websiteBucket,
  cacheControl: [
    s3deploy.CacheControl.maxAge(cdk.Duration.minutes(5)), // Short TTL
    s3deploy.CacheControl.mustRevalidate(),
  ],
  prune: false, // Don't delete other files
});
```

**Cache Strategy**:
- TTL: 5 minutes (balance between freshness and performance)
- Must revalidate: Ensures clients check for updates
- No aggressive caching: Configuration changes should propagate quickly

### 2. Angular Application Changes

#### 2.1 Configuration Service

**Location**: `frontend/ai.client/src/app/services/config.service.ts`

**Purpose**: Centralized runtime configuration management

```typescript
import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export interface RuntimeConfig {
  appApiUrl: string;
  inferenceApiUrl: string;
  enableAuthentication: boolean;
  environment: string;
}

@Injectable({ providedIn: 'root' })
export class ConfigService {
  private readonly http = inject(HttpClient);
  
  // Signal to store configuration
  private readonly config = signal<RuntimeConfig | null>(null);
  
  // Computed signals for easy access
  readonly appApiUrl = computed(() => this.config()?.appApiUrl ?? '');
  readonly inferenceApiUrl = computed(() => this.config()?.inferenceApiUrl ?? '');
  readonly enableAuthentication = computed(() => this.config()?.enableAuthentication ?? true);
  readonly environment = computed(() => this.config()?.environment ?? 'development');
  
  // Loading state
  private readonly isLoaded = signal(false);
  readonly loaded = this.isLoaded.asReadonly();
  
  /**
   * Load configuration from /config.json
   * Called by APP_INITIALIZER before app bootstrap
   */
  async loadConfig(): Promise<void> {
    try {
      // Attempt to fetch runtime config
      const config = await firstValueFrom(
        this.http.get<RuntimeConfig>('/config.json')
      );
      
      this.validateConfig(config);
      this.config.set(config);
      this.isLoaded.set(true);
      
      console.log('✅ Runtime configuration loaded:', config.environment);
    } catch (error) {
      console.warn('⚠️ Failed to load runtime config, using fallback:', error);
      
      // Fallback to environment.ts for local development
      const fallbackConfig: RuntimeConfig = {
        appApiUrl: environment.appApiUrl || 'http://localhost:8000',
        inferenceApiUrl: environment.inferenceApiUrl || '',
        enableAuthentication: environment.enableAuthentication ?? false,
        environment: environment.production ? 'production' : 'development',
      };
      
      this.config.set(fallbackConfig);
      this.isLoaded.set(true);
    }
  }
  
  /**
   * Validate configuration has required fields
   */
  private validateConfig(config: any): asserts config is RuntimeConfig {
    if (!config.appApiUrl || typeof config.appApiUrl !== 'string') {
      throw new Error('Invalid config: appApiUrl is required');
    }
    if (!config.inferenceApiUrl || typeof config.inferenceApiUrl !== 'string') {
      throw new Error('Invalid config: inferenceApiUrl is required');
    }
    if (typeof config.enableAuthentication !== 'boolean') {
      throw new Error('Invalid config: enableAuthentication must be boolean');
    }
  }
  
  /**
   * Get a configuration value by key
   */
  get<K extends keyof RuntimeConfig>(key: K): RuntimeConfig[K] {
    const value = this.config()?.[key];
    if (value === undefined) {
      throw new Error(`Configuration not loaded or key '${key}' not found`);
    }
    return value;
  }
}
```

**Key Features**:
- Signal-based reactive state
- Computed signals for easy access
- Validation of required fields
- Fallback to environment.ts for local dev
- Type-safe configuration access

#### 2.2 Application Initializer

**Location**: `frontend/ai.client/src/app/app.config.ts`

**Purpose**: Load configuration before app bootstrap

```typescript
import { ApplicationConfig, APP_INITIALIZER } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ConfigService } from './services/config.service';

/**
 * Factory function to load configuration
 */
function initializeApp(configService: ConfigService) {
  return () => configService.loadConfig();
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(
      withInterceptors([/* existing interceptors */])
    ),
    
    // Load configuration before app starts
    {
      provide: APP_INITIALIZER,
      useFactory: initializeApp,
      deps: [ConfigService],
      multi: true,
    },
    
    // ... other providers
  ],
};
```

**Execution Flow**:
1. Angular starts bootstrap process
2. APP_INITIALIZER runs `configService.loadConfig()`
3. HTTP request to `/config.json` is made
4. Configuration is validated and stored
5. App bootstrap continues
6. All services can now access configuration

#### 2.3 Update Existing Services

**Services to Update**:
- `ApiService` - Use `ConfigService.appApiUrl()`
- `AuthService` - Use `ConfigService.enableAuthentication()`
- Any service making HTTP requests to backend

**Example Migration**:

```typescript
// BEFORE
import { environment } from '@environments/environment';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.appApiUrl;
}

// AFTER
import { ConfigService } from './config.service';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly config = inject(ConfigService);
  private readonly baseUrl = computed(() => this.config.appApiUrl());
}
```

#### 2.4 Environment Files (Backward Compatibility)

**Keep environment.ts for local development**:

```typescript
// frontend/ai.client/src/environments/environment.ts
export const environment = {
  production: false,
  appApiUrl: 'http://localhost:8000',
  inferenceApiUrl: 'http://localhost:8001',
  enableAuthentication: false,
};
```

**Production environment.ts becomes minimal**:

```typescript
// frontend/ai.client/src/environments/environment.production.ts
export const environment = {
  production: true,
  // Runtime values loaded from config.json
  appApiUrl: '',
  inferenceApiUrl: '',
  enableAuthentication: true,
};
```

### 3. Deployment Pipeline Changes

#### 3.1 Remove Manual Configuration Steps

**Current GitHub Actions Workflow**:
```yaml
# .github/workflows/frontend.yml
- name: Deploy Frontend
  env:
    APP_API_URL: ${{ secrets.APP_API_URL }}  # ❌ Remove
    INFERENCE_API_URL: ${{ secrets.INFERENCE_API_URL }}  # ❌ Remove
```

**New GitHub Actions Workflow**:
```yaml
# .github/workflows/frontend.yml
- name: Deploy Frontend
  run: |
    cd infrastructure
    npx cdk deploy FrontendStack --require-approval never
```

**No environment-specific configuration needed** - values come from SSM

#### 3.2 Deployment Order

**Required Order**:
1. InfrastructureStack (creates VPC, ALB, exports ALB URL to SSM)
2. AppApiStack (uses ALB)
3. InferenceApiStack (exports Runtime URL to SSM)
4. FrontendStack (reads SSM, generates config.json, deploys)

**Dependency Management**:
- Frontend stack deployment script should verify backend stacks are deployed
- Use CDK stack dependencies if deploying with `--all`

### 4. Local Development Setup

#### 4.1 Local config.json

**Location**: `frontend/ai.client/public/config.json`

**Content** (for local development):
```json
{
  "appApiUrl": "http://localhost:8000",
  "inferenceApiUrl": "http://localhost:8001",
  "enableAuthentication": false,
  "environment": "local"
}
```

**Add to .gitignore**:
```
# Local development config
/frontend/ai.client/public/config.json
```

#### 4.2 Development Documentation

**README.md addition**:
```markdown
## Local Development

### Option 1: Use local config.json (Recommended)
1. Copy `public/config.json.example` to `public/config.json`
2. Update URLs to point to your local backend
3. Run `npm start`

### Option 2: Use environment.ts fallback
1. Ensure `src/environments/environment.ts` has correct local URLs
2. Run `npm start` (config.json fetch will fail, fallback activates)
```

## Data Flow

### Configuration Loading Sequence

```
1. Browser requests index.html
   └─> CloudFront serves index.html

2. Angular bootstrap starts
   └─> APP_INITIALIZER triggered

3. ConfigService.loadConfig() called
   └─> HTTP GET /config.json
       ├─> Success: Parse and validate
       │   └─> Store in signal
       │       └─> App continues
       │
       └─> Failure: Use environment.ts fallback
           └─> Store fallback in signal
               └─> App continues

4. Services access configuration
   └─> ConfigService.appApiUrl()
   └─> ConfigService.inferenceApiUrl()
```

### Configuration Update Flow

```
1. Infrastructure change (e.g., new ALB URL)
   └─> CDK deploy updates SSM parameter

2. Frontend stack deployment
   └─> Reads new SSM value
   └─> Generates new config.json
   └─> Deploys to S3

3. CloudFront cache invalidation (optional)
   └─> Or wait for 5-minute TTL

4. User refreshes browser
   └─> Fetches new config.json
   └─> App uses new URLs
```

## Error Handling

### Configuration Fetch Failures

**Scenario 1: Network Error**
- Retry with exponential backoff (3 attempts)
- Fall back to environment.ts
- Log warning to console
- App continues with fallback

**Scenario 2: Invalid JSON**
- Log error with details
- Fall back to environment.ts
- App continues with fallback

**Scenario 3: Missing Required Fields**
- Validation throws error
- Fall back to environment.ts
- App continues with fallback

### Runtime Configuration Errors

**Scenario 4: Invalid URL at Runtime**
- HTTP interceptor catches 404/500 errors
- Display user-friendly error message
- Provide retry mechanism
- Log error for debugging

## Security Considerations

### 1. Configuration Exposure
- **Risk**: config.json is publicly accessible
- **Mitigation**: Only include non-sensitive URLs (no API keys, secrets)
- **Note**: URLs are not considered sensitive (already visible in network traffic)

### 2. Configuration Tampering
- **Risk**: User modifies config.json in browser
- **Mitigation**: 
  - Validate configuration on backend
  - Use HTTPS to prevent MITM attacks
  - Backend enforces authentication regardless of client config

### 3. Cache Poisoning
- **Risk**: Malicious config.json cached by CDN
- **Mitigation**:
  - Short TTL (5 minutes)
  - CloudFront signed URLs (if needed)
  - S3 bucket policies restrict write access

## Performance Considerations

### 1. Initial Load Time
- **Impact**: +1 HTTP request at startup (~50-100ms)
- **Mitigation**: 
  - Small file size (~200 bytes)
  - Served from CloudFront edge locations
  - Parallel loading with other assets

### 2. Cache Strategy
- **TTL**: 5 minutes (balance freshness vs performance)
- **Revalidation**: Must-revalidate header
- **Browser Cache**: Respect CloudFront cache headers

### 3. Fallback Performance
- **Scenario**: config.json fetch fails
- **Impact**: ~3 second delay (retry attempts)
- **Mitigation**: Fast timeout, immediate fallback

## Testing Strategy

### Unit Tests

**ConfigService Tests**:
```typescript
describe('ConfigService', () => {
  it('should load configuration from /config.json', async () => {
    // Mock HTTP response
    // Call loadConfig()
    // Assert config is set
  });
  
  it('should fall back to environment.ts on fetch failure', async () => {
    // Mock HTTP error
    // Call loadConfig()
    // Assert fallback config is used
  });
  
  it('should validate required fields', async () => {
    // Mock invalid config
    // Call loadConfig()
    // Assert validation error and fallback
  });
});
```

### Integration Tests

**End-to-End Tests**:
```typescript
describe('Runtime Configuration', () => {
  it('should load config and make API calls', () => {
    cy.visit('/');
    cy.intercept('/config.json').as('config');
    cy.wait('@config');
    cy.get('[data-testid="app-loaded"]').should('exist');
  });
  
  it('should handle config fetch failure gracefully', () => {
    cy.intercept('/config.json', { forceNetworkError: true });
    cy.visit('/');
    cy.get('[data-testid="app-loaded"]').should('exist');
  });
});
```

### Manual Testing

**Test Cases**:
1. Deploy with valid configuration → App loads successfully
2. Deploy with invalid JSON → App falls back to environment.ts
3. Deploy with missing fields → App falls back to environment.ts
4. Update backend URL → New config propagates within 5 minutes
5. Local development → App uses local config.json or environment.ts

## Migration Plan

### Phase 1: Infrastructure Preparation
1. Update InfrastructureStack to export ALB URL to SSM
2. Update InferenceApiStack to export Runtime URL to SSM
3. Deploy infrastructure changes
4. Verify SSM parameters are populated

### Phase 2: Frontend Implementation
1. Create ConfigService with signal-based state
2. Add APP_INITIALIZER to app.config.ts
3. Update existing services to use ConfigService
4. Add unit tests for ConfigService
5. Test locally with mock config.json

### Phase 3: Frontend Stack Update
1. Update FrontendStack to read SSM parameters
2. Add config.json generation logic
3. Deploy config.json with appropriate cache headers
4. Test deployment to dev environment

### Phase 4: Pipeline Update
1. Remove manual configuration from GitHub Actions
2. Update deployment scripts
3. Test full deployment pipeline
4. Document new deployment process

### Phase 5: Rollout
1. Deploy to dev environment
2. Validate configuration loading
3. Deploy to staging environment
4. Validate configuration loading
5. Deploy to production environment
6. Monitor for issues

## Rollback Plan

**If issues occur**:
1. Revert frontend deployment (CloudFormation rollback)
2. Frontend falls back to environment.ts (backward compatible)
3. Investigate and fix issues
4. Redeploy when ready

**Backward Compatibility**:
- Keep environment.ts files with fallback values
- ConfigService handles missing config.json gracefully
- No breaking changes to existing services

## Open Questions & Decisions

### Q1: Should config.json include feature flags?
**Decision**: Not in initial implementation. Add in future enhancement if needed.

### Q2: What cache TTL for config.json?
**Decision**: 5 minutes (balance between freshness and performance)

### Q3: Should we support environment-specific overrides?
**Decision**: No. Single config.json per deployment. Use separate deployments for different environments.

### Q4: How to handle blue/green deployments?
**Decision**: Each deployment has its own config.json. No special handling needed.

### Q5: Should we URL-encode the Runtime ARN in CDK or in the app?
**Decision**: In the app. CDK stores the raw URL, Angular encodes the ARN portion when making requests.

## Success Criteria

- ✅ Zero manual steps in deployment pipeline
- ✅ Frontend builds are environment-agnostic
- ✅ Configuration updates don't require rebuilds
- ✅ Local development works without AWS infrastructure
- ✅ Backward compatible with existing deployments
- ✅ All tests pass (unit, integration, e2e)
- ✅ Documentation is complete and accurate

## Future Enhancements

1. **Dynamic Configuration Updates**: WebSocket or polling for real-time config updates
2. **Configuration Versioning**: Track config changes over time
3. **Feature Flags**: Add feature flag support to config.json
4. **Multi-Region Support**: Region-specific configuration
5. **Configuration Encryption**: Encrypt sensitive values (if needed)
6. **Configuration Validation**: Backend endpoint to validate config.json

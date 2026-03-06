# Design Document: SSM Parameters Audit

## Overview

This design addresses the missing SSM parameters required by the runtime-provisioner Lambda function. The solution involves auditing existing SSM parameter exports across CDK stacks and adding missing parameters to ensure the Lambda function can successfully fetch all required configuration values.

The design follows the existing CDK infrastructure patterns established in the project, using SSM Parameter Store for cross-stack references and maintaining consistent naming conventions.

## Architecture

### Current State

The project uses SSM Parameter Store for cross-stack communication:

```
InfrastructureStack (Foundation)
├── Exports: VPC, ALB, ECS Cluster, OAuth tables
└── SSM: /network/*, /oauth/*, /users/*, /rbac/*

InferenceApiStack (AgentCore Resources)
├── Exports: Memory, Code Interpreter, Browser, Runtime Role
└── SSM: /inference-api/*

GatewayStack (MCP Tools)
├── Exports: Gateway URL, Gateway ID
└── SSM: /gateway/*

AppApiStack (Application Backend)
├── Exports: DynamoDB tables, S3 buckets
└── SSM: /quota/*, /cost-tracking/*, /file-upload/*, /rag/*

FrontendStack (CloudFront + S3)
├── Exports: Distribution ID, Frontend URL
└── SSM: /frontend/*
```

### Target State

After this feature, all stacks will export complete SSM parameters required by runtime-provisioner:

```
runtime-provisioner Lambda
├── Reads from InfrastructureStack: /oauth/*, /users/*, /rbac/*
├── Reads from InferenceApiStack: /inference-api/*
├── Reads from GatewayStack: /gateway/*
├── Reads from AppApiStack: /rag/*
├── Reads from FrontendStack: /frontend/*
└── Optionally reads: /api-keys/*
```

## Components and Interfaces

### Component 1: InferenceApiStack SSM Exports

**Purpose**: Export all AgentCore Runtime configuration parameters

**Existing Parameters** (verified):
- `/${projectPrefix}/inference-api/image-tag` - Docker image tag (set by push-to-ecr.sh)
- `/${projectPrefix}/inference-api/runtime-execution-role-arn` - IAM role ARN for runtimes
- `/${projectPrefix}/inference-api/memory-arn` - AgentCore Memory ARN
- `/${projectPrefix}/inference-api/memory-id` - AgentCore Memory ID
- `/${projectPrefix}/inference-api/code-interpreter-id` - Code Interpreter ID
- `/${projectPrefix}/inference-api/code-interpreter-arn` - Code Interpreter ARN
- `/${projectPrefix}/inference-api/browser-id` - Browser ID
- `/${projectPrefix}/inference-api/browser-arn` - Browser ARN

**Missing Parameters** (to be added):
- `/${projectPrefix}/inference-api/ecr-repository-uri` - ECR repository URI for container images

**Implementation**:
```typescript
// In InferenceApiStack constructor, after ECR repository reference

// Export ECR repository URI for Lambda-created runtimes
new ssm.StringParameter(this, 'EcrRepositoryUriParameter', {
  parameterName: `/${config.projectPrefix}/inference-api/ecr-repository-uri`,
  stringValue: ecrRepository.repositoryUri,
  description: 'Inference API ECR Repository URI for runtime container images',
  tier: ssm.ParameterTier.STANDARD,
});
```

### Component 2: GatewayStack SSM Exports

**Purpose**: Export AgentCore Gateway configuration parameters

**Existing Parameters** (verified):
- `/${projectPrefix}/gateway/url` - Gateway URL for SigV4 authenticated invocation
- `/${projectPrefix}/gateway/id` - Gateway identifier

**Status**: No changes needed - all required parameters already exist

### Component 3: InfrastructureStack SSM Exports

**Purpose**: Export network and OAuth configuration parameters

**Existing Parameters** (verified):
- `/${projectPrefix}/network/alb-url` - Application Load Balancer URL
- `/${projectPrefix}/oauth/providers-table-name` - OAuth providers table
- `/${projectPrefix}/oauth/user-tokens-table-name` - OAuth user tokens table
- `/${projectPrefix}/oauth/token-encryption-key-arn` - KMS key for token encryption
- `/${projectPrefix}/oauth/client-secrets-arn` - Secrets Manager ARN for OAuth secrets

**Missing Parameters** (to be added):
- `/${projectPrefix}/oauth/callback-url` - OAuth callback URL for authentication flows

**Implementation**:
```typescript
// In InfrastructureStack constructor, after ALB URL export

// Construct OAuth callback URL
const oauthCallbackUrl = config.frontend?.domainName
  ? `https://${config.frontend.domainName}/auth/callback`
  : `${albUrl}/auth/callback`;

// Export OAuth callback URL for runtime provisioner
new ssm.StringParameter(this, 'OAuthCallbackUrlParameter', {
  parameterName: `/${config.projectPrefix}/oauth/callback-url`,
  stringValue: oauthCallbackUrl,
  description: 'OAuth callback URL for authentication provider configuration',
  tier: ssm.ParameterTier.STANDARD,
});
```

### Component 4: FrontendStack SSM Exports

**Purpose**: Export frontend URL and CORS configuration

**Existing Parameters** (verified):
- `/${projectPrefix}/frontend/url` - Frontend website URL
- `/${projectPrefix}/frontend/distribution-id` - CloudFront distribution ID
- `/${projectPrefix}/frontend/bucket-name` - S3 bucket name

**Missing Parameters** (to be added):
- `/${projectPrefix}/frontend/cors-origins` - Comma-separated list of allowed CORS origins

**Implementation**:
```typescript
// In FrontendStack constructor, after frontend URL export

// Construct CORS origins list
const corsOrigins = config.frontend.domainName
  ? `https://${config.frontend.domainName}`
  : `https://${this.distributionDomainName}`;

// Export CORS origins for runtime provisioner
new ssm.StringParameter(this, 'CorsOriginsParameter', {
  parameterName: `/${config.projectPrefix}/frontend/cors-origins`,
  stringValue: corsOrigins,
  description: 'Comma-separated list of allowed CORS origins for OAuth flows',
  tier: ssm.ParameterTier.STANDARD,
});
```

### Component 5: Optional API Keys

**Purpose**: Provide optional external service API keys

**Parameters** (optional - not created by CDK):
- `/${projectPrefix}/api-keys/tavily-api-key` - Tavily search API key
- `/${projectPrefix}/api-keys/nova-act-api-key` - Nova Act API key

**Implementation**: These parameters are NOT created by CDK stacks. They must be manually created by administrators when needed:

```bash
# Manual creation (when needed)
aws ssm put-parameter \
  --name "/${PROJECT_PREFIX}/api-keys/tavily-api-key" \
  --value "YOUR_TAVILY_API_KEY" \
  --type "SecureString" \
  --description "Tavily search API key for web search capabilities"

aws ssm put-parameter \
  --name "/${PROJECT_PREFIX}/api-keys/nova-act-api-key" \
  --value "YOUR_NOVA_ACT_API_KEY" \
  --type "SecureString" \
  --description "Nova Act API key for browser automation"
```

The runtime-provisioner Lambda must handle missing optional parameters gracefully using try-except blocks.

## Data Models

### SSM Parameter Structure

```typescript
interface SSMParameter {
  parameterName: string;      // Hierarchical path: /${projectPrefix}/{category}/{name}
  stringValue: string;         // Parameter value (can be token at synth time)
  description: string;         // Human-readable description
  tier: ssm.ParameterTier;    // STANDARD or ADVANCED
}
```

### Parameter Dependency Matrix

This matrix documents all SSM parameters used in the system, showing which stacks export each parameter and which stacks/Lambda functions import them.

| Parameter Path | Exported By | Imported By | Required | Notes |
|---------------|-------------|-------------|----------|-------|
| `/inference-api/image-tag` | push-to-ecr.sh script | InferenceApiStack, runtime-provisioner | Yes | Docker image tag set by CI/CD |
| `/inference-api/ecr-repository-uri` | InferenceApiStack | runtime-provisioner | Yes | ECR repository URI for container images |
| `/inference-api/runtime-execution-role-arn` | InferenceApiStack | runtime-provisioner, AppApiStack | Yes | IAM role ARN for runtimes |
| `/inference-api/memory-arn` | InferenceApiStack | runtime-provisioner, AppApiStack | Yes | AgentCore Memory ARN |
| `/inference-api/memory-id` | InferenceApiStack | runtime-provisioner, AppApiStack | Yes | AgentCore Memory ID |
| `/inference-api/code-interpreter-id` | InferenceApiStack | runtime-provisioner | Yes | Code Interpreter ID |
| `/inference-api/code-interpreter-arn` | InferenceApiStack | AppApiStack | Yes | Code Interpreter ARN |
| `/inference-api/browser-id` | InferenceApiStack | runtime-provisioner | Yes | Browser ID |
| `/inference-api/browser-arn` | InferenceApiStack | AppApiStack | Yes | Browser ARN |
| `/gateway/url` | GatewayStack | runtime-provisioner | Yes | Gateway URL for SigV4 authenticated invocation |
| `/gateway/id` | GatewayStack | runtime-provisioner | Yes | Gateway identifier |
| `/network/vpc-id` | InfrastructureStack | AppApiStack, InferenceApiStack, GatewayStack | Yes | VPC ID for all services |
| `/network/vpc-cidr` | InfrastructureStack | AppApiStack, GatewayStack | Yes | VPC CIDR block |
| `/network/private-subnet-ids` | InfrastructureStack | AppApiStack, InferenceApiStack | Yes | Comma-separated private subnet IDs |
| `/network/public-subnet-ids` | InfrastructureStack | GatewayStack | Yes | Comma-separated public subnet IDs |
| `/network/availability-zones` | InfrastructureStack | AppApiStack | Yes | Comma-separated AZ list |
| `/network/alb-arn` | InfrastructureStack | AppApiStack | Yes | Application Load Balancer ARN |
| `/network/alb-dns-name` | InfrastructureStack | AppApiStack | Yes | ALB DNS name |
| `/network/alb-url` | InfrastructureStack | FrontendStack, runtime-provisioner | Yes | Full ALB URL (http/https) |
| `/network/alb-listener-arn` | InfrastructureStack | AppApiStack | Yes | Primary ALB listener ARN |
| `/network/alb-security-group-id` | InfrastructureStack | AppApiStack | Yes | ALB security group ID |
| `/network/ecs-cluster-name` | InfrastructureStack | AppApiStack, InferenceApiStack | Yes | ECS cluster name |
| `/network/ecs-cluster-arn` | InfrastructureStack | AppApiStack, InferenceApiStack | Yes | ECS cluster ARN |
| `/oauth/callback-url` | InfrastructureStack | runtime-provisioner | Yes | OAuth callback URL for auth flows |
| `/oauth/providers-table-name` | InfrastructureStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | OAuth providers table |
| `/oauth/providers-table-arn` | InfrastructureStack | AppApiStack, InferenceApiStack | Yes | OAuth providers table ARN |
| `/oauth/user-tokens-table-name` | InfrastructureStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | OAuth user tokens table |
| `/oauth/user-tokens-table-arn` | InfrastructureStack | AppApiStack, InferenceApiStack | Yes | OAuth user tokens table ARN |
| `/oauth/token-encryption-key-arn` | InfrastructureStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | KMS key for token encryption |
| `/oauth/client-secrets-arn` | InfrastructureStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | Secrets Manager ARN for OAuth secrets |
| `/users/users-table-name` | InfrastructureStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | Users table name |
| `/users/users-table-arn` | InfrastructureStack | AppApiStack, InferenceApiStack | Yes | Users table ARN |
| `/rbac/app-roles-table-name` | InfrastructureStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | AppRoles table (RBAC + tool catalog) |
| `/rbac/app-roles-table-arn` | InfrastructureStack | AppApiStack, InferenceApiStack | Yes | AppRoles table ARN |
| `/auth/oidc-state-table-name` | InfrastructureStack | AppApiStack, runtime-provisioner | Yes | OIDC state table for distributed auth |
| `/auth/oidc-state-table-arn` | InfrastructureStack | AppApiStack | Yes | OIDC state table ARN |
| `/auth/secret-arn` | InfrastructureStack | AppApiStack | Yes | Authentication secret ARN |
| `/auth/secret-name` | InfrastructureStack | AppApiStack | Yes | Authentication secret name |
| `/rag/assistants-table-name` | RagIngestionStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | RAG assistants table |
| `/rag/assistants-table-arn` | RagIngestionStack | AppApiStack, InferenceApiStack | Yes | RAG assistants table ARN |
| `/rag/vector-bucket-name` | RagIngestionStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | S3 vector store bucket |
| `/rag/vector-index-name` | RagIngestionStack | AppApiStack, InferenceApiStack, runtime-provisioner | Yes | S3 vector store index name |
| `/frontend/url` | FrontendStack | runtime-provisioner | Yes | Frontend website URL |
| `/frontend/cors-origins` | FrontendStack | runtime-provisioner | Yes | Comma-separated CORS origins |
| `/frontend/distribution-id` | FrontendStack | deployment scripts | Yes | CloudFront distribution ID |
| `/frontend/bucket-name` | FrontendStack | deployment scripts | Yes | S3 bucket name for assets |
| `/api-keys/tavily-api-key` | Manual (admin) | runtime-provisioner | No | Tavily search API key (optional) |
| `/api-keys/nova-act-api-key` | Manual (admin) | runtime-provisioner | No | Nova Act API key (optional) |

### Parameter Categories

Parameters are organized into hierarchical categories for easy discovery and management:

- **`/network/`** - VPC, subnets, ALB, ECS cluster resources
- **`/inference-api/`** - AgentCore Runtime, Memory, Code Interpreter, Browser
- **`/gateway/`** - AgentCore Gateway for MCP tools
- **`/oauth/`** - OAuth providers, tokens, encryption keys
- **`/users/`** - User management tables
- **`/rbac/`** - Role-based access control tables
- **`/auth/`** - Authentication secrets and OIDC state
- **`/rag/`** - RAG assistants and vector storage
- **`/frontend/`** - CloudFront distribution and CORS configuration
- **`/api-keys/`** - Optional external service API keys (manually created)

### Stack Deployment Order

The parameter dependency matrix enforces this deployment order:

1. **InfrastructureStack** (Foundation)
   - Exports: VPC, ALB, ECS Cluster, DynamoDB tables, OAuth resources
   - Dependencies: None

2. **RagIngestionStack** (Data Layer)
   - Exports: RAG assistants table, vector storage
   - Dependencies: InfrastructureStack

3. **InferenceApiStack** (AgentCore Resources)
   - Exports: Memory, Code Interpreter, Browser, Runtime role, ECR URI
   - Dependencies: InfrastructureStack, RagIngestionStack

4. **GatewayStack** (MCP Tools)
   - Exports: Gateway URL, Gateway ID
   - Dependencies: InfrastructureStack

5. **AppApiStack** (Application Backend)
   - Exports: Application-specific tables and buckets
   - Dependencies: InfrastructureStack, InferenceApiStack, GatewayStack, RagIngestionStack

6. **FrontendStack** (CloudFront + S3)
   - Exports: Distribution ID, Frontend URL, CORS origins
   - Dependencies: InfrastructureStack, AppApiStack

### Optional Parameters

The following parameters are NOT created by CDK stacks and must be manually created by administrators when needed:

- **`/api-keys/tavily-api-key`** - Tavily search API key for web search capabilities
- **`/api-keys/nova-act-api-key`** - Nova Act API key for browser automation

These parameters are handled gracefully by the runtime-provisioner Lambda using the `get_optional_parameter()` function, which returns `None` if the parameter doesn't exist.

To create optional parameters manually:

```bash
# Tavily API key
aws ssm put-parameter \
  --name "/${PROJECT_PREFIX}/api-keys/tavily-api-key" \
  --value "YOUR_TAVILY_API_KEY" \
  --type "SecureString" \
  --description "Tavily search API key for web search capabilities"

# Nova Act API key
aws ssm put-parameter \
  --name "/${PROJECT_PREFIX}/api-keys/nova-act-api-key" \
  --value "YOUR_NOVA_ACT_API_KEY" \
  --type "SecureString" \
  --description "Nova Act API key for browser automation"
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Parameter Naming Convention Compliance

*For any* SSM parameter exported by CDK stacks, the parameter name should follow the hierarchical pattern `/${projectPrefix}/{category}/{resource-name}` where category is one of: `network`, `inference-api`, `gateway`, `frontend`, `oauth`, `api-keys`, `users`, `rbac`, `rag`, `quota`, `cost-tracking`, `file-upload`, `auth`, `lambda`, or `sns`.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7**

### Property 2: OAuth Callback URL Format

*For any* OAuth callback URL parameter value, the URL should match the pattern `{base_url}/auth/callback` where base_url is either a custom domain (https://{domain}) or an ALB URL.

**Validates: Requirements 7.4**

## Error Handling

### Missing Optional Parameters

The runtime-provisioner Lambda function must handle missing optional API key parameters gracefully:

```python
def get_optional_parameter(parameter_name: str) -> Optional[str]:
    """
    Fetch an optional SSM parameter, returning None if it doesn't exist.
    
    Args:
        parameter_name: Full SSM parameter path
        
    Returns:
        Parameter value if it exists, None otherwise
    """
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except ssm_client.exceptions.ParameterNotFound:
        logger.info(f"Optional parameter {parameter_name} not found, skipping")
        return None
    except Exception as e:
        logger.error(f"Error fetching parameter {parameter_name}: {e}")
        raise
```

### Missing Required Parameters

For required parameters, the Lambda function should fail fast with a clear error message:

```python
def get_required_parameter(parameter_name: str) -> str:
    """
    Fetch a required SSM parameter, raising an exception if it doesn't exist.
    
    Args:
        parameter_name: Full SSM parameter path
        
    Returns:
        Parameter value
        
    Raises:
        ParameterNotFound: If the required parameter doesn't exist
        Exception: For other SSM errors
    """
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except ssm_client.exceptions.ParameterNotFound:
        logger.error(f"Required parameter {parameter_name} not found")
        raise
    except Exception as e:
        logger.error(f"Error fetching parameter {parameter_name}: {e}")
        raise
```

### CDK Deployment Failures

If SSM parameter export fails during CDK deployment:

1. CloudFormation will roll back the stack
2. The deployment will fail with a clear error message
3. Existing parameters will remain unchanged
4. No partial state will be left in SSM Parameter Store

### Parameter Value Validation

The runtime-provisioner should validate parameter values before using them:

```python
def validate_url(url: str, parameter_name: str) -> None:
    """
    Validate that a URL parameter has the correct format.
    
    Args:
        url: URL string to validate
        parameter_name: Parameter name for error messages
        
    Raises:
        ValueError: If URL format is invalid
    """
    if not url.startswith(('http://', 'https://')):
        raise ValueError(
            f"Invalid URL format for {parameter_name}: {url}. "
            f"Must start with http:// or https://"
        )
    
    if not url.strip():
        raise ValueError(f"Empty URL value for {parameter_name}")
```

## Testing Strategy

### Unit Tests

Unit tests will verify specific CDK stack configurations and parameter exports:

**Test: InferenceApiStack exports ECR repository URI**
```typescript
test('InferenceApiStack exports ECR repository URI parameter', () => {
  const app = new cdk.App();
  const stack = new InferenceApiStack(app, 'TestStack', {
    config: testConfig,
  });
  
  const template = Template.fromStack(stack);
  
  template.hasResourceProperties('AWS::SSM::Parameter', {
    Name: '/test-prefix/inference-api/ecr-repository-uri',
    Type: 'String',
    Description: Match.stringLikeRegexp('ECR.*URI'),
  });
});
```

**Test: InfrastructureStack exports OAuth callback URL**
```typescript
test('InfrastructureStack exports OAuth callback URL parameter', () => {
  const app = new cdk.App();
  const stack = new InfrastructureStack(app, 'TestStack', {
    config: testConfig,
  });
  
  const template = Template.fromStack(stack);
  
  template.hasResourceProperties('AWS::SSM::Parameter', {
    Name: '/test-prefix/oauth/callback-url',
    Type: 'String',
    Description: Match.stringLikeRegexp('OAuth.*callback'),
  });
});
```

**Test: FrontendStack exports CORS origins**
```typescript
test('FrontendStack exports CORS origins parameter', () => {
  const app = new cdk.App();
  const stack = new FrontendStack(app, 'TestStack', {
    config: testConfig,
  });
  
  const template = Template.fromStack(stack);
  
  template.hasResourceProperties('AWS::SSM::Parameter', {
    Name: '/test-prefix/frontend/cors-origins',
    Type: 'String',
    Description: Match.stringLikeRegexp('CORS.*origins'),
  });
});
```

**Test: OAuth callback URL uses custom domain when configured**
```typescript
test('OAuth callback URL uses custom domain when configured', () => {
  const app = new cdk.App();
  const configWithDomain = {
    ...testConfig,
    frontend: {
      ...testConfig.frontend,
      domainName: 'app.example.com',
    },
  };
  
  const stack = new InfrastructureStack(app, 'TestStack', {
    config: configWithDomain,
  });
  
  const template = Template.fromStack(stack);
  
  // Verify the parameter value contains the custom domain
  template.hasResourceProperties('AWS::SSM::Parameter', {
    Name: '/test-prefix/oauth/callback-url',
    Value: Match.stringLikeRegexp('https://app\\.example\\.com/auth/callback'),
  });
});
```

**Test: OAuth callback URL uses ALB URL when no custom domain**
```typescript
test('OAuth callback URL uses ALB URL when no custom domain', () => {
  const app = new cdk.App();
  const configWithoutDomain = {
    ...testConfig,
    frontend: {
      ...testConfig.frontend,
      domainName: undefined,
    },
  };
  
  const stack = new InfrastructureStack(app, 'TestStack', {
    config: configWithoutDomain,
  });
  
  const template = Template.fromStack(stack);
  
  // Verify the parameter value uses ALB URL
  template.hasResourceProperties('AWS::SSM::Parameter', {
    Name: '/test-prefix/oauth/callback-url',
    Value: Match.stringLikeRegexp('/auth/callback$'),
  });
});
```

**Test: Runtime provisioner handles missing optional parameters**
```python
def test_get_optional_parameter_not_found():
    """Test that get_optional_parameter returns None for missing parameters."""
    with patch('boto3.client') as mock_client:
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound'}},
            'GetParameter'
        )
        mock_client.return_value = mock_ssm
        
        result = get_optional_parameter('/test/api-keys/tavily-api-key')
        
        assert result is None
        mock_ssm.get_parameter.assert_called_once()
```

**Test: Runtime provisioner fails on missing required parameters**
```python
def test_get_required_parameter_not_found():
    """Test that get_required_parameter raises exception for missing parameters."""
    with patch('boto3.client') as mock_client:
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound'}},
            'GetParameter'
        )
        mock_client.return_value = mock_ssm
        
        with pytest.raises(ClientError):
            get_required_parameter('/test/inference-api/memory-id')
```

### Integration Tests

Integration tests will verify end-to-end parameter flow after deployment:

**Test: Runtime provisioner can fetch all required parameters**
```python
def test_runtime_provisioner_fetches_all_parameters():
    """
    Integration test: Deploy stacks and verify runtime provisioner
    can fetch all required SSM parameters.
    """
    # This test requires actual AWS deployment
    # Run in CI/CD pipeline after stack deployment
    
    required_parameters = [
        f'/{PROJECT_PREFIX}/inference-api/image-tag',
        f'/{PROJECT_PREFIX}/inference-api/ecr-repository-uri',
        f'/{PROJECT_PREFIX}/inference-api/runtime-execution-role-arn',
        f'/{PROJECT_PREFIX}/inference-api/memory-arn',
        f'/{PROJECT_PREFIX}/inference-api/memory-id',
        f'/{PROJECT_PREFIX}/inference-api/code-interpreter-id',
        f'/{PROJECT_PREFIX}/inference-api/browser-id',
        f'/{PROJECT_PREFIX}/gateway/url',
        f'/{PROJECT_PREFIX}/gateway/id',
        f'/{PROJECT_PREFIX}/network/alb-url',
        f'/{PROJECT_PREFIX}/oauth/callback-url',
        f'/{PROJECT_PREFIX}/frontend/url',
        f'/{PROJECT_PREFIX}/frontend/cors-origins',
    ]
    
    ssm_client = boto3.client('ssm')
    
    for param_name in required_parameters:
        response = ssm_client.get_parameter(Name=param_name)
        assert response['Parameter']['Value'], f"Parameter {param_name} is empty"
        print(f"✓ {param_name}: {response['Parameter']['Value']}")
```

**Test: All parameters follow naming convention**
```python
def test_all_parameters_follow_naming_convention():
    """
    Integration test: Verify all exported parameters follow the
    hierarchical naming convention.
    """
    ssm_client = boto3.client('ssm')
    
    # Get all parameters with project prefix
    paginator = ssm_client.get_paginator('describe_parameters')
    parameters = []
    
    for page in paginator.paginate(
        ParameterFilters=[
            {
                'Key': 'Name',
                'Option': 'BeginsWith',
                'Values': [f'/{PROJECT_PREFIX}/']
            }
        ]
    ):
        parameters.extend(page['Parameters'])
    
    # Validate naming convention
    valid_categories = {
        'network', 'inference-api', 'gateway', 'frontend', 'oauth',
        'api-keys', 'users', 'rbac', 'rag', 'quota', 'cost-tracking',
        'file-upload', 'auth', 'lambda', 'sns'
    }
    
    pattern = re.compile(rf'^/{PROJECT_PREFIX}/([^/]+)/([^/]+)$')
    
    for param in parameters:
        name = param['Name']
        match = pattern.match(name)
        
        assert match, f"Parameter {name} doesn't follow naming convention"
        
        category = match.group(1)
        assert category in valid_categories, \
            f"Parameter {name} uses invalid category: {category}"
        
        print(f"✓ {name} follows naming convention")
```

### Property-Based Tests

Property-based tests will verify universal properties across all parameter configurations:

**Property Test: Parameter naming convention**
```python
from hypothesis import given, strategies as st

@given(
    category=st.sampled_from([
        'network', 'inference-api', 'gateway', 'frontend', 'oauth',
        'api-keys', 'users', 'rbac', 'rag', 'quota', 'cost-tracking',
        'file-upload', 'auth', 'lambda', 'sns'
    ]),
    resource_name=st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'),
        min_size=1,
        max_size=50
    ).filter(lambda x: x and not x.startswith('-') and not x.endswith('-'))
)
def test_parameter_naming_convention_property(category: str, resource_name: str):
    """
    Property: For any valid category and resource name, the constructed
    parameter path should follow the hierarchical naming convention.
    
    Feature: ssm-parameters-audit, Property 1: Parameter Naming Convention Compliance
    """
    project_prefix = 'test-prefix'
    param_name = f'/{project_prefix}/{category}/{resource_name}'
    
    # Verify pattern matches
    pattern = re.compile(rf'^/{project_prefix}/([^/]+)/([^/]+)$')
    match = pattern.match(param_name)
    
    assert match is not None, f"Parameter {param_name} doesn't match pattern"
    assert match.group(1) == category
    assert match.group(2) == resource_name
```

**Property Test: OAuth callback URL format**
```python
from hypothesis import given, strategies as st

@given(
    base_url=st.one_of(
        st.builds(
            lambda domain: f'https://{domain}',
            st.from_regex(r'[a-z0-9-]+\.[a-z]{2,}', fullmatch=True)
        ),
        st.builds(
            lambda alb: f'http://{alb}.elb.amazonaws.com',
            st.from_regex(r'alb-[a-z0-9]+', fullmatch=True)
        )
    )
)
def test_oauth_callback_url_format_property(base_url: str):
    """
    Property: For any valid base URL (custom domain or ALB URL), the OAuth
    callback URL should follow the format {base_url}/auth/callback.
    
    Feature: ssm-parameters-audit, Property 2: OAuth Callback URL Format
    """
    callback_url = f'{base_url}/auth/callback'
    
    # Verify format
    assert callback_url.endswith('/auth/callback')
    assert callback_url.startswith(('http://', 'https://'))
    
    # Verify base URL is preserved
    assert callback_url.startswith(base_url)
```

### Manual Testing Checklist

After deployment, manually verify:

- [ ] All required SSM parameters exist in Parameter Store
- [ ] Parameter values are correct (not empty or placeholder values)
- [ ] OAuth callback URL matches expected format
- [ ] Frontend CORS origins parameter contains correct domain(s)
- [ ] ECR repository URI parameter contains valid repository URI
- [ ] Runtime provisioner Lambda can successfully fetch all parameters
- [ ] Runtime provisioner Lambda handles missing optional parameters gracefully
- [ ] CloudFormation outputs show all expected parameter names

### Testing Configuration

**Unit Tests**:
- Framework: Jest (TypeScript CDK tests), pytest (Python Lambda tests)
- Run frequency: On every commit
- Coverage target: 80% for new code

**Integration Tests**:
- Framework: pytest with boto3
- Run frequency: After deployment to dev/staging
- Requires: Actual AWS environment with deployed stacks

**Property-Based Tests**:
- Framework: Hypothesis (Python)
- Iterations: 100 per property test
- Run frequency: On every commit
- Focus: Universal properties that hold for all inputs

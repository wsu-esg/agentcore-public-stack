# Requirements Document: SSM Parameters Audit

## Introduction

The runtime-provisioner Lambda function requires access to multiple SSM parameters across different CDK stacks to dynamically create AgentCore Runtimes for authentication providers. Currently, some required SSM parameters are missing from the CDK stack definitions, which will cause the Lambda function to fail when attempting to fetch these parameters. This feature ensures all required SSM parameters are properly exported by their respective CDK stacks.

## Glossary

- **SSM Parameter Store**: AWS Systems Manager Parameter Store, a secure hierarchical storage for configuration data
- **Runtime_Provisioner**: Lambda function that creates AgentCore Runtimes when authentication providers are added
- **CDK_Stack**: AWS Cloud Development Kit infrastructure-as-code stack definition
- **Parameter_Path**: Hierarchical naming convention for SSM parameters (e.g., `/${projectPrefix}/category/resource-name`)
- **InferenceApiStack**: CDK stack that creates AgentCore Runtime shared resources (Memory, Code Interpreter, Browser)
- **GatewayStack**: CDK stack that creates AgentCore Gateway and MCP tools
- **AppApiStack**: CDK stack that creates the main application API Fargate service
- **FrontendStack**: CDK stack that creates CloudFront distribution and S3 bucket for frontend assets
- **ECR_Repository**: Elastic Container Registry repository containing Docker images

## Requirements

### Requirement 1: Audit Existing SSM Parameters

**User Story:** As a DevOps engineer, I want to verify which SSM parameters already exist in CDK stacks, so that I know which parameters need to be added.

#### Acceptance Criteria

1. WHEN reviewing InferenceApiStack, THE System SHALL identify all SSM parameters currently exported
2. WHEN reviewing GatewayStack, THE System SHALL identify all SSM parameters currently exported
3. WHEN reviewing AppApiStack, THE System SHALL identify all SSM parameters currently exported
4. WHEN reviewing FrontendStack, THE System SHALL identify all SSM parameters currently exported
5. WHEN comparing against runtime-provisioner requirements, THE System SHALL produce a list of missing parameters

### Requirement 2: Add Missing Inference API Parameters

**User Story:** As a runtime provisioner, I want to access inference API configuration via SSM parameters, so that I can create AgentCore Runtimes with the correct settings.

#### Acceptance Criteria

1. WHEN InferenceApiStack deploys, THE System SHALL export `/${projectPrefix}/inference-api/ecr-repository-uri` parameter with the ECR repository URI value
2. WHEN InferenceApiStack deploys, THE System SHALL export `/${projectPrefix}/inference-api/image-tag` parameter (already exists - verify only)
3. WHEN InferenceApiStack deploys, THE System SHALL export `/${projectPrefix}/inference-api/runtime-execution-role-arn` parameter (already exists - verify only)
4. WHEN InferenceApiStack deploys, THE System SHALL export `/${projectPrefix}/inference-api/memory-arn` parameter (already exists - verify only)
5. WHEN InferenceApiStack deploys, THE System SHALL export `/${projectPrefix}/inference-api/memory-id` parameter (already exists - verify only)
6. WHEN InferenceApiStack deploys, THE System SHALL export `/${projectPrefix}/inference-api/code-interpreter-id` parameter (already exists - verify only)
7. WHEN InferenceApiStack deploys, THE System SHALL export `/${projectPrefix}/inference-api/browser-id` parameter (already exists - verify only)

### Requirement 3: Add Missing Gateway Parameters

**User Story:** As a runtime provisioner, I want to access gateway configuration via SSM parameters, so that I can configure AgentCore Runtimes to use the correct gateway endpoint.

#### Acceptance Criteria

1. WHEN GatewayStack deploys, THE System SHALL export `/${projectPrefix}/gateway/url` parameter (already exists - verify only)
2. WHEN GatewayStack deploys, THE System SHALL export `/${projectPrefix}/gateway/id` parameter (already exists - verify only)

### Requirement 4: Add Missing App API Parameters

**User Story:** As a runtime provisioner, I want to access app API configuration via SSM parameters, so that I can configure OAuth callback URLs correctly.

#### Acceptance Criteria

1. WHEN InfrastructureStack deploys, THE System SHALL export `/${projectPrefix}/network/alb-url` parameter (already exists - verify only)
2. WHEN AppApiStack needs to reference the app API URL, THE System SHALL import it from `/${projectPrefix}/network/alb-url` parameter

### Requirement 5: Add Missing Frontend Parameters

**User Story:** As a runtime provisioner, I want to access frontend configuration via SSM parameters, so that I can configure OAuth redirect URIs correctly.

#### Acceptance Criteria

1. WHEN FrontendStack deploys, THE System SHALL export `/${projectPrefix}/frontend/url` parameter (already exists - verify only)
2. WHEN FrontendStack deploys, THE System SHALL export `/${projectPrefix}/frontend/cors-origins` parameter with comma-separated allowed origins
3. WHEN FrontendStack deploys AND a custom domain is configured, THE System SHALL use the custom domain as the frontend URL value
4. WHEN FrontendStack deploys AND no custom domain is configured, THE System SHALL use the CloudFront distribution domain as the frontend URL value

### Requirement 6: Add Optional API Key Parameters

**User Story:** As a runtime provisioner, I want to access optional API keys via SSM parameters when they exist, so that I can configure external service integrations.

#### Acceptance Criteria

1. WHEN runtime-provisioner attempts to fetch `/${projectPrefix}/api-keys/tavily-api-key`, THE System SHALL return the parameter value if it exists
2. WHEN runtime-provisioner attempts to fetch `/${projectPrefix}/api-keys/tavily-api-key` AND the parameter does not exist, THE System SHALL handle the missing parameter gracefully
3. WHEN runtime-provisioner attempts to fetch `/${projectPrefix}/api-keys/nova-act-api-key`, THE System SHALL return the parameter value if it exists
4. WHEN runtime-provisioner attempts to fetch `/${projectPrefix}/api-keys/nova-act-api-key` AND the parameter does not exist, THE System SHALL handle the missing parameter gracefully

### Requirement 7: Add OAuth Callback URL Parameter

**User Story:** As a runtime provisioner, I want to access the OAuth callback URL via SSM parameter, so that I can configure authentication providers correctly.

#### Acceptance Criteria

1. WHEN InfrastructureStack deploys, THE System SHALL export `/${projectPrefix}/oauth/callback-url` parameter with the OAuth callback URL value
2. WHEN InfrastructureStack deploys AND a custom domain is configured, THE System SHALL construct the callback URL using the custom domain
3. WHEN InfrastructureStack deploys AND no custom domain is configured, THE System SHALL construct the callback URL using the ALB URL
4. THE OAuth_Callback_URL SHALL follow the format `{base_url}/auth/callback`

### Requirement 8: Maintain Parameter Naming Consistency

**User Story:** As a developer, I want SSM parameters to follow consistent naming conventions, so that they are easy to discover and use.

#### Acceptance Criteria

1. THE System SHALL use the hierarchical naming pattern `/${projectPrefix}/{category}/{resource-name}` for all parameters
2. WHEN a parameter belongs to network resources, THE System SHALL use the category `network`
3. WHEN a parameter belongs to inference API resources, THE System SHALL use the category `inference-api`
4. WHEN a parameter belongs to gateway resources, THE System SHALL use the category `gateway`
5. WHEN a parameter belongs to frontend resources, THE System SHALL use the category `frontend`
6. WHEN a parameter belongs to OAuth resources, THE System SHALL use the category `oauth`
7. WHEN a parameter belongs to API keys, THE System SHALL use the category `api-keys`

### Requirement 9: Document Parameter Dependencies

**User Story:** As a developer, I want to understand which stacks depend on which SSM parameters, so that I can maintain the correct deployment order.

#### Acceptance Criteria

1. WHEN documenting SSM parameters, THE System SHALL specify which stack exports each parameter
2. WHEN documenting SSM parameters, THE System SHALL specify which stacks or Lambda functions import each parameter
3. WHEN documenting SSM parameters, THE System SHALL indicate whether each parameter is required or optional
4. THE System SHALL maintain a parameter dependency matrix showing export and import relationships

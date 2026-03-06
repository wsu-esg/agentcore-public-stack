---
inclusion: fileMatch
fileMatchPattern: "infrastructure/**/*.{ts,js,json}"
---

# AWS CDK Infrastructure Best Practices

Apply these patterns when working with CDK stacks, constructs, or any infrastructure-as-code in this project.

## TypeScript

- Use strict type checking
- Import from `aws-cdk-lib` and `constructs`
- Use L2 constructs when available, L1 (Cfn*) when necessary

## Stack Organization

```
infrastructure/
├── bin/infrastructure.ts          # App entrypoint
├── lib/
│   ├── config.ts                  # Configuration loader
│   ├── infrastructure-stack.ts    # Network resources (deploy first)
│   ├── app-api-stack.ts           # Backend services
│   └── my-new-stack.ts            # New stacks go here
└── cdk.context.json               # Configuration
```

**Deployment Order:**
1. `InfrastructureStack` - VPC, ALB, ECS Cluster (always first)
2. Other stacks import network resources via SSM

## Configuration

Use the centralized config system:

```typescript
import { loadConfig, getResourceName, getStackEnv, applyStandardTags } from './config';

export class MyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    const config = loadConfig(scope);
    super(scope, id, {
      ...props,
      env: getStackEnv(config),
      stackName: getResourceName(config, 'my-stack'),
    });
    applyStandardTags(this, config);
  }
}
```

For configuration patterns, see #[[file:cdk-configuration.md]]

## Naming Conventions

**Resource Names:** Use `getResourceName()`:
```typescript
getResourceName(config, 'user-quotas')  // "bsu-agentcore-user-quotas"
```

**SSM Parameters:** Hierarchical naming:
```
/{projectPrefix}/{category}/{resource-type}
```

Categories: `/network/`, `/quota/`, `/cost-tracking/`, `/auth/`, `/frontend/`, `/gateway/`

## Cross-Stack References

**Export:**
```typescript
new ssm.StringParameter(this, 'VpcIdParam', {
  parameterName: `/${config.projectPrefix}/network/vpc-id`,
  stringValue: vpc.vpcId,
});
```

**Import:**
```typescript
const vpcId = ssm.StringParameter.valueForStringParameter(
  this,
  `/${config.projectPrefix}/network/vpc-id`
);
```

## Resource Patterns

### DynamoDB Tables

- Always use PK + SK for flexibility
- Use `PAY_PER_REQUEST` billing
- Enable point-in-time recovery
- Environment-based removal policy

For table patterns, see #[[file:cdk-dynamodb.md]]

### ECS/Fargate

- Import cluster from SSM
- Health checks mandatory
- Auto-scaling with CPU/memory targets
- Circuit breaker for rollback

For service patterns, see #[[file:cdk-ecs-fargate.md]]

### Lambda

- Use ARM64 architecture (cost optimization)
- Role with least privilege
- Secrets Manager access requires wildcard suffix

For Lambda patterns, see #[[file:cdk-lambda.md]]

### S3 Buckets

- Block public access
- Enable versioning
- Lifecycle rules for cost optimization
- Include account ID for global uniqueness

For bucket patterns, see #[[file:cdk-s3.md]]

### Networking

- VPC with public and private subnets
- Security groups with least privilege
- ALB with HTTPS and health checks
- VPC endpoints for cost optimization

For networking patterns, see #[[file:cdk-networking.md]]

## Security

- Separate security groups for ALB and ECS
- Private subnets for services
- IAM roles with SIDs for clarity
- Never hardcode secrets

For IAM patterns, see #[[file:cdk-iam.md]]

## Bedrock AgentCore

- Memory, Gateway, Code Interpreter, Browser
- Use underscores in names, not hyphens
- Proper role configuration for each service
- Export IDs/ARNs to SSM for backend access

For AgentCore patterns, see #[[file:cdk-agentcore.md]]

## Important Constraints

**AgentCore Names:** Use underscores, not hyphens:
```typescript
name: getResourceName(config, 'memory').replace(/-/g, '_')
```

**Secrets Manager ARN:** Include wildcard for random suffix:
```typescript
resources: [`${secret.secretArn}*`]
```

**Environment Removal Policy:**
```typescript
removalPolicy: config.environment === 'prod'
  ? cdk.RemovalPolicy.RETAIN
  : cdk.RemovalPolicy.DESTROY
```

## CDK Commands

```bash
cd infrastructure
npm install           # Install dependencies
npx cdk synth         # Synthesize CloudFormation
npx cdk deploy --all  # Deploy all stacks
npx cdk diff          # Preview changes
```

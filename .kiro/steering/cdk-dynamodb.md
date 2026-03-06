---
inclusion: manual
---

# DynamoDB Table Patterns

## Standard Table Structure

```typescript
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { getResourceName } from './config';

const table = new dynamodb.Table(this, 'UserQuotasTable', {
  tableName: getResourceName(config, 'user-quotas'),

  // Always use PK + SK for flexibility
  partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },

  // PAY_PER_REQUEST for variable workloads
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,

  // Production safety
  pointInTimeRecovery: true,
  encryption: dynamodb.TableEncryption.AWS_MANAGED,

  // Environment-based retention
  removalPolicy: config.environment === 'prod'
    ? cdk.RemovalPolicy.RETAIN
    : cdk.RemovalPolicy.DESTROY,
});
```

## GSI Pattern

```typescript
// GSI naming: DescriptiveNameIndex
// GSI keys: GSI{n}PK / GSI{n}SK
table.addGlobalSecondaryIndex({
  indexName: 'OwnerStatusIndex',
  partitionKey: { name: 'GSI1PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'GSI1SK', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.ALL,
});

table.addGlobalSecondaryIndex({
  indexName: 'EmailDomainIndex',
  partitionKey: { name: 'GSI2PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'GSI2SK', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.ALL,
});
```

## TTL Configuration

```typescript
// For ephemeral data (sessions, auth state)
const table = new dynamodb.Table(this, 'OidcStateTable', {
  tableName: getResourceName(config, 'oidc-state'),
  partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,

  // Enable TTL for automatic expiration
  timeToLiveAttribute: 'ttl',  // or 'expiresAt'

  removalPolicy: cdk.RemovalPolicy.DESTROY,
});
```

## Table Key Patterns

Use composite keys with type prefixes:

| Pattern | Example | Use Case |
|---------|---------|----------|
| `USER#{id}` | `USER#abc123` | User-scoped data |
| `SESSION#{id}` | `SESSION#sess-001` | Session data |
| `ROLE#{id}` | `ROLE#admin` | Role definitions |
| `QUOTA#{type}` | `QUOTA#monthly` | Quota tiers |
| `TIMESTAMP#{ts}` | `TIMESTAMP#2024-01-15T10:30:00Z` | Time-ordered data |
| `MESSAGE#{id}` | `MESSAGE#msg-001` | Message records |
| `CONFIG` | `CONFIG` | Configuration record |

## Exporting Table Names to SSM

```typescript
// Export table name for cross-stack reference
new ssm.StringParameter(this, 'UserQuotasTableNameParam', {
  parameterName: `/${config.projectPrefix}/quota/user-quotas-table-name`,
  stringValue: userQuotasTable.tableName,
  description: 'User quotas DynamoDB table name',
});
```

## Granting Access

```typescript
// In ECS task definition
userQuotasTable.grantReadWriteData(taskDefinition.taskRole);

// Read-only access
quotaEventsTable.grantReadData(taskDefinition.taskRole);
```

# Session Deletion & Schema Refactoring Specification

## Executive Summary

This specification outlines a schema refactoring to enable session deletion while preserving cost accounting accuracy. The current `SessionsMetadata` table uses SK patterns that conflate session metadata with per-message cost data, creating performance issues and preventing clean session deletion.

**Goal**: Allow users to delete conversations without disrupting quota enforcement, cost reports, or audit trails.

**Approach**: Refactor SK patterns in the existing `SessionsMetadata` table to cleanly separate session records from cost records, enabling efficient queries and soft delete support.

**Key Decision**: Use single-table design (no new tables) with updated SK prefixes for optimal operational simplicity.

**Impact**: No user-facing or admin-facing functionality changes. Performance improvements for session listing.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Current Architecture](#current-architecture)
3. [Proposed Architecture](#proposed-architecture)
4. [Schema Design](#schema-design)
5. [Session Deletion Flow](#session-deletion-flow)
6. [Impact Analysis](#impact-analysis)
7. [Implementation Plan](#implementation-plan)
8. [Implementation Details](#implementation-details)
9. [API Changes](#api-changes)
10. [Testing Strategy](#testing-strategy)

---

## Problem Statement

### Current Issues

1. **Session and Message Records Mixed**: The `SessionsMetadata` table stores both:
   - Session records: `SK = SESSION#{session_id}`
   - Message cost records: `SK = SESSION#{session_id}#MSG#{message_id}`

   Both start with `SESSION#`, so `begins_with(SK, 'SESSION#')` matches both. Listing sessions requires filtering out message records in memory.

2. **No Session Deletion**: Deleting a session would orphan cost records or break audit trails.

3. **Performance Degradation**: A user with 100 sessions and 10,000 messages returns ~10,100 items when listing sessions, then filters 10,000 in memory.

4. **No Server-Side Pagination**: Sessions must be sorted by `last_message_at` in memory because DynamoDB pagination follows SK order.

### Business Requirements

| Requirement | Priority | Notes |
|-------------|----------|-------|
| Users can delete conversations | HIGH | Privacy, cleanup |
| Deleted sessions don't appear in session list | HIGH | User expectation |
| Cost accounting remains accurate after deletion | HIGH | Billing integrity |
| Quota enforcement unaffected by deletion | HIGH | Quota uses pre-aggregated data |
| Audit trail preserved for compliance | MEDIUM | Financial records retention |
| Admin can view costs for deleted sessions | LOW | Investigation capability |

---

## Current Architecture

### SessionsMetadata Table (Current SK Patterns)

```
Table: SessionsMetadata
─────────────────────────────────────────────────────────────────────────
PK                    │ SK                                    │ Type
─────────────────────────────────────────────────────────────────────────
USER#{user_id}        │ SESSION#{session_id}                  │ Session metadata
USER#{user_id}        │ SESSION#{session_id}#MSG#00001        │ Message cost
USER#{user_id}        │ SESSION#{session_id}#MSG#00002        │ Message cost
USER#{user_id}        │ SESSION#{session_id}#MSG#00003        │ Message cost
...
─────────────────────────────────────────────────────────────────────────
```

### Problems with Current Design

```python
# Current list_user_sessions implementation (simplified)
async def _list_user_sessions_cloud(...):
    # Query returns BOTH session and message records
    response = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":prefix": "SESSION#"  # Matches both SESSION#{id} and SESSION#{id}#MSG#
        }
    )

    sessions = []
    for item in response['Items']:
        # Filter out message records in memory
        if '#MSG#' in item.get('SK', ''):
            continue  # Skip message records
        sessions.append(item)

    # Sort in memory (can't use DynamoDB for this)
    sessions.sort(key=lambda x: x.last_message_at, reverse=True)

    return sessions[:limit]  # Pagination is fake
```

**Complexity**: O(m + s) where m = messages, s = sessions

---

## Proposed Architecture

### Single-Table Design with New SK Prefixes

Instead of creating new tables, we refactor the SK patterns in the existing `SessionsMetadata` table:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CURRENT SK PATTERNS                              │
├─────────────────────────────────────────────────────────────────────────┤
│  SESSION#{session_id}                  ← Session metadata                │
│  SESSION#{session_id}#MSG#00001        ← Message cost                    │
│  SESSION#{session_id}#MSG#00002        ← Message cost                    │
│                                                                          │
│  Problem: Both start with "SESSION#" - can't query sessions only        │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         NEW SK PATTERNS                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  S#ACTIVE#{last_message_at}#{session_id}    ← Active session             │
│  S#DELETED#{deleted_at}#{session_id}        ← Soft-deleted session       │
│  C#{timestamp}#{uuid}                        ← Message cost record       │
│                                                                          │
│  Benefits:                                                               │
│  - Query sessions: begins_with(SK, 'S#ACTIVE#')                         │
│  - Query costs: begins_with(SK, 'C#')                                   │
│  - Sessions sorted by timestamp in SK                                   │
│  - No in-memory filtering or sorting needed                             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Single-Table Design?

| Factor | Single Table | Multiple Tables |
|--------|--------------|-----------------|
| **Query efficiency** | Same (with proper SK prefixes) | Same |
| **Operational complexity** | Lower (1 table to manage) | Higher (3 tables, 3 sets of alarms) |
| **Backup/restore** | Simpler (1 backup) | More complex |
| **Cost** | Slightly lower (fewer table overheads) | Slightly higher |
| **TTL handling** | Only cost records get `ttl` attribute | Clean separation |
| **Code clarity** | Requires SK prefix discipline | Natural separation |

**Recommendation**: Single-table design for operational simplicity. The SK prefix approach provides the same query efficiency with less infrastructure overhead.

---

## Schema Design

### SessionsMetadata Table (Refactored SK Patterns)

**Same table, new SK patterns:**

```
Table: SessionsMetadata (existing table, refactored)
─────────────────────────────────────────────────────────────────────────
PK                    │ SK                                         │ Type
─────────────────────────────────────────────────────────────────────────
USER#{user_id}        │ S#ACTIVE#{last_message_at}#{session_id}    │ Active session
USER#{user_id}        │ S#DELETED#{deleted_at}#{session_id}        │ Deleted session
USER#{user_id}        │ C#{timestamp}#{uuid}                       │ Message cost
─────────────────────────────────────────────────────────────────────────
```

### Session Record Attributes

```python
{
    # Keys
    "PK": "USER#alice",
    "SK": "S#ACTIVE#2025-01-15T10:30:00Z#abc123",

    # GSI keys for direct session lookup
    "GSI_PK": "SESSION#abc123",
    "GSI_SK": "META",

    # Session data
    "sessionId": "abc123",
    "userId": "alice",
    "title": "Conversation about weather",
    "status": "active",
    "createdAt": "2025-01-15T09:00:00Z",
    "lastMessageAt": "2025-01-15T10:30:00Z",
    "messageCount": 15,

    # User preferences
    "starred": False,
    "tags": ["weather", "planning"],
    "preferences": {
        "lastModel": "claude-sonnet-4-5",
        "lastTemperature": 0.7,
        "enabledTools": ["weather", "search"]
    },

    # Soft delete fields (only present when deleted)
    "deleted": False,
    "deletedAt": None

    # NOTE: No TTL attribute - sessions persist until soft-deleted
}
```

### Cost Record Attributes

```python
{
    # Keys
    "PK": "USER#alice",
    "SK": "C#2025-01-15T10:30:45.123Z#550e8400-e29b-41d4-a716-446655440000",

    # GSI keys for per-session cost queries
    "GSI_PK": "SESSION#abc123",
    "GSI_SK": "C#2025-01-15T10:30:45.123Z",

    # Session reference
    "sessionId": "abc123",
    "messageId": 5,

    # Cost data
    "cost": 0.0234,
    "inputTokens": 1000,
    "outputTokens": 500,
    "cacheReadTokens": 200,
    "cacheWriteTokens": 100,

    # Model info
    "modelId": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "modelName": "Claude 3.5 Sonnet",
    "provider": "bedrock",

    # Pricing snapshot
    "pricingSnapshot": {
        "inputPricePerMtok": 3.0,
        "outputPricePerMtok": 15.0,
        "cacheReadPricePerMtok": 0.30,
        "cacheWritePricePerMtok": 3.75,
        "currency": "USD",
        "snapshotAt": "2025-01-15T10:30:45Z"
    },

    # Latency
    "timeToFirstToken": 250,
    "endToEndLatency": 1500,

    # Attribution
    "userId": "alice",
    "timestamp": "2025-01-15T10:30:45.123Z",

    # TTL - ONLY cost records have this attribute
    "ttl": 1768118400  # 365 days from creation
}
```

### SK Pattern Design Rationale

| SK Pattern | Purpose | Benefits |
|------------|---------|----------|
| `S#ACTIVE#{last_message_at}#{session_id}` | Active sessions | Sorted by recency, clean prefix query |
| `S#DELETED#{deleted_at}#{session_id}` | Soft-deleted sessions | Separate from active, queryable for admin |
| `C#{timestamp}#{uuid}` | Cost records | Time-ordered, unique, supports TTL |

### TTL Handling in Single Table

DynamoDB TTL only deletes items that have the `ttl` attribute set:

```python
# Session records: NO ttl attribute → persist indefinitely (until soft-deleted)
session_item = {
    "PK": "USER#alice",
    "SK": "S#ACTIVE#2025-01-15T10:30:00Z#abc123",
    # No "ttl" attribute
}

# Cost records: HAVE ttl attribute → auto-delete after 365 days
cost_item = {
    "PK": "USER#alice",
    "SK": "C#2025-01-15T10:30:45.123Z#uuid",
    "ttl": int((datetime.now() + timedelta(days=365)).timestamp())
}
```

### GSI: SessionLookupIndex

For direct session access by ID and per-session cost queries:

```
GSI: SessionLookupIndex
  PK: GSI_PK (e.g., SESSION#{session_id})
  SK: GSI_SK (e.g., META for sessions, C#{timestamp} for costs)

Projection: ALL
```

**Access Patterns via GSI:**

```python
# Get session by ID (without knowing status or timestamp)
response = table.query(
    IndexName="SessionLookupIndex",
    KeyConditionExpression="GSI_PK = :pk AND GSI_SK = :sk",
    ExpressionAttributeValues={
        ":pk": f"SESSION#{session_id}",
        ":sk": "META"
    }
)

# Get all costs for a specific session
response = table.query(
    IndexName="SessionLookupIndex",
    KeyConditionExpression="GSI_PK = :pk AND begins_with(GSI_SK, :prefix)",
    ExpressionAttributeValues={
        ":pk": f"SESSION#{session_id}",
        ":prefix": "C#"
    }
)
```

### Access Patterns (Primary Table)

```python
# 1. List active sessions (sorted by most recent) - O(page_size)
response = table.query(
    KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
    ExpressionAttributeValues={
        ":pk": f"USER#{user_id}",
        ":prefix": "S#ACTIVE#"
    },
    ScanIndexForward=False,  # Descending order (most recent first)
    Limit=20,
    ExclusiveStartKey=pagination_token  # Native DynamoDB pagination works!
)

# 2. List deleted sessions (for admin/recovery)
response = table.query(
    KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
    ExpressionAttributeValues={
        ":pk": f"USER#{user_id}",
        ":prefix": "S#DELETED#"
    },
    ScanIndexForward=False,
    Limit=20
)

# 3. Get user costs in date range (for detailed reports)
response = table.query(
    KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
    ExpressionAttributeValues={
        ":pk": f"USER#{user_id}",
        ":start": f"C#{start_date}",
        ":end": f"C#{end_date}~"  # ~ sorts after any timestamp
    }
)
```

---

## Session Deletion Flow

### Soft Delete Process

```python
async def delete_session(user_id: str, session_id: str) -> None:
    """
    Soft-delete a session while preserving cost records.

    Steps:
    1. Get current session to find its SK
    2. Transactionally move from S#ACTIVE# to S#DELETED# prefix
    3. Delete conversation content from AgentCore Memory
    4. Cost records (C# prefix) remain untouched
    """
    now = datetime.now(timezone.utc)

    # 1. Get current session via GSI
    session = await get_session_by_id(user_id, session_id)
    if not session:
        raise NotFoundError(f"Session {session_id} not found")

    if session.deleted:
        return  # Already deleted

    # 2. Build old and new SKs
    old_sk = f"S#ACTIVE#{session.last_message_at}#{session_id}"
    new_sk = f"S#DELETED#{now.isoformat()}#{session_id}"

    # 3. Transactional move: delete old + create new
    dynamodb.transact_write_items(
        TransactItems=[
            {
                'Delete': {
                    'TableName': 'SessionsMetadata',
                    'Key': {
                        'PK': f'USER#{user_id}',
                        'SK': old_sk
                    },
                    'ConditionExpression': 'attribute_exists(PK)'
                }
            },
            {
                'Put': {
                    'TableName': 'SessionsMetadata',
                    'Item': {
                        'PK': f'USER#{user_id}',
                        'SK': new_sk,
                        'GSI_PK': f'SESSION#{session_id}',
                        'GSI_SK': 'META',
                        'sessionId': session_id,
                        'userId': user_id,
                        'title': session.title,
                        'status': 'deleted',
                        'createdAt': session.created_at,
                        'lastMessageAt': session.last_message_at,
                        'messageCount': session.message_count,
                        'starred': session.starred,
                        'tags': session.tags,
                        'preferences': session.preferences,
                        'deleted': True,
                        'deletedAt': now.isoformat()
                    }
                }
            }
        ]
    )

    # 4. Delete conversation content from AgentCore Memory (async)
    # This removes the actual messages but NOT the cost records
    await agentcore_memory.delete_session(session_id)

    logger.info(f"Soft-deleted session {session_id} for user {user_id}")
```

### What Happens to Each Data Type

| Data Type | SK Pattern | After Deletion |
|-----------|------------|----------------|
| Session metadata | `S#ACTIVE#...` → `S#DELETED#...` | Moved to deleted prefix |
| Conversation content | AgentCore Memory | **Deleted** (user expectation) |
| Per-message costs | `C#...` | **Preserved** (audit trail, unchanged) |
| User cost summary | `UserCostSummary` table | **Unchanged** (pre-aggregated) |
| System rollups | `SystemCostRollup` table | **Unchanged** |

---

## Impact Analysis

### User Features

| Feature | Before | After | Impact |
|---------|--------|-------|--------|
| List sessions | Filter in memory, sort in memory | Query `S#ACTIVE#` prefix | **Much faster** |
| Get session | Query by old SK | Query GSI by session ID | Same |
| Update session | Update item | Transact if `lastMessageAt` changes | Slightly more complex |
| Delete session | Not supported | Soft delete | **New feature** |
| View cost summary | `UserCostSummary` | `UserCostSummary` | Unchanged |
| Detailed cost report | Query `SESSION#...#MSG#` | Query `C#` prefix | Same |
| Quota enforcement | `UserCostSummary` | `UserCostSummary` | Unchanged |

### Admin Features

| Feature | Before | After | Impact |
|---------|--------|-------|--------|
| System summary | `SystemCostRollup` | `SystemCostRollup` | Unchanged |
| Top users by cost | `UserCostSummary` GSI | `UserCostSummary` GSI | Unchanged |
| Cost by model | Query `SESSION#...#MSG#` | Query `C#` prefix | Same |
| Cost trends | Query `SESSION#...#MSG#` | Query `C#` prefix | Same |
| Per-session costs | Query by session prefix | Query GSI `SESSION#{id}` + `C#` | Same |
| View deleted sessions | Not supported | Query `S#DELETED#` prefix | **New feature** |

### Performance Comparison

| Operation | Current | After Refactor |
|-----------|---------|----------------|
| List 20 sessions (user with 100 sessions, 10k messages) | O(10,100) query + O(100) filter + O(100) sort | **O(20) query** |
| Get session by ID | O(1) | O(1) via GSI |
| Delete session | N/A | O(1) transact write |
| Per-session costs | O(m) query | O(m) query via GSI |
| Quota check | O(1) | O(1) |

---

## Implementation Plan

Since the application is not yet in production, this is a **greenfield implementation** rather than a migration.

### Phase 1: Add GSI to Existing Table

Add the `SessionLookupIndex` GSI to `SessionsMetadata`:

```bash
aws dynamodb update-table \
    --table-name SessionsMetadata \
    --attribute-definitions \
        AttributeName=GSI_PK,AttributeType=S \
        AttributeName=GSI_SK,AttributeType=S \
    --global-secondary-index-updates \
        "[{
            \"Create\": {
                \"IndexName\": \"SessionLookupIndex\",
                \"KeySchema\": [
                    {\"AttributeName\":\"GSI_PK\",\"KeyType\":\"HASH\"},
                    {\"AttributeName\":\"GSI_SK\",\"KeyType\":\"RANGE\"}
                ],
                \"Projection\": {\"ProjectionType\":\"ALL\"}
            }
        }]"
```

### Phase 2: Update Backend Code

Refactor code to use new SK patterns:

| File | Changes |
|------|---------|
| `backend/src/apis/app_api/sessions/services/metadata.py` | New SK patterns for sessions and costs |
| `backend/src/apis/app_api/sessions/routes.py` | Add `DELETE /sessions/{id}` endpoint |
| `backend/src/apis/app_api/costs/aggregator.py` | Query `C#` prefix instead of `SESSION#...#MSG#` |
| `backend/src/apis/app_api/admin/costs/routes.py` | Update queries for cost reports |

### Phase 3: Frontend Changes

Add delete functionality:

| File | Changes |
|------|---------|
| `session.service.ts` | Add `deleteSession()` method |
| Session list component | Add delete button with confirmation |

---

## Implementation Details

### Updated store_session_metadata

```python
# backend/src/apis/app_api/sessions/services/metadata.py

async def _store_session_metadata_cloud(
    session_id: str,
    user_id: str,
    session_metadata: SessionMetadata,
    table_name: str
) -> None:
    """
    Store session metadata with new SK pattern.

    Schema:
        PK: USER#{user_id}
        SK: S#ACTIVE#{last_message_at}#{session_id}

    GSI: SessionLookupIndex
        GSI_PK: SESSION#{session_id}
        GSI_SK: META
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # Prepare item
    item = session_metadata.model_dump(by_alias=True, exclude_none=True)
    item = _convert_floats_to_decimal(item)

    last_message_at = session_metadata.last_message_at or datetime.now(timezone.utc).isoformat()

    # Build keys with new pattern
    item['PK'] = f'USER#{user_id}'
    item['SK'] = f'S#ACTIVE#{last_message_at}#{session_id}'

    # GSI keys for direct lookup
    item['GSI_PK'] = f'SESSION#{session_id}'
    item['GSI_SK'] = 'META'

    # Note: NO ttl attribute - sessions persist until soft-deleted

    table.put_item(Item=item)
    logger.info(f"Stored session metadata: {session_id}")
```

### Updated store_message_metadata

```python
async def _store_message_metadata_cloud(
    session_id: str,
    user_id: str,
    message_id: int,
    message_metadata: MessageMetadata,
    table_name: str
) -> None:
    """
    Store message metadata with new SK pattern.

    Schema:
        PK: USER#{user_id}
        SK: C#{timestamp}#{uuid}

    GSI: SessionLookupIndex
        GSI_PK: SESSION#{session_id}
        GSI_SK: C#{timestamp}
    """
    import uuid as uuid_lib
    from datetime import datetime, timezone, timedelta

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    metadata_dict = message_metadata.model_dump(by_alias=True, exclude_none=True)
    metadata_decimal = _convert_floats_to_decimal(metadata_dict)

    timestamp = metadata_dict.get("attribution", {}).get(
        "timestamp",
        datetime.now(timezone.utc).isoformat()
    )

    # Generate unique SK
    unique_id = str(uuid_lib.uuid4())

    # TTL: 365 days (only cost records have TTL)
    ttl = int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp())

    item = {
        # Primary key with new pattern
        "PK": f"USER#{user_id}",
        "SK": f"C#{timestamp}#{unique_id}",

        # GSI keys for per-session queries
        "GSI_PK": f"SESSION#{session_id}",
        "GSI_SK": f"C#{timestamp}",

        # Session reference
        "sessionId": session_id,
        "messageId": message_id,

        # Attribution
        "userId": user_id,
        "timestamp": timestamp,

        # TTL - only cost records have this
        "ttl": ttl,

        # Metadata
        **metadata_decimal
    }

    table.put_item(Item=item)

    # Update cost summary (unchanged)
    await _update_cost_summary_async(
        user_id=user_id,
        timestamp=timestamp,
        message_metadata=message_metadata
    )
```

### Updated list_user_sessions

```python
async def _list_user_sessions_cloud(
    user_id: str,
    table_name: str,
    limit: Optional[int] = None,
    next_token: Optional[str] = None
) -> Tuple[list[SessionMetadata], Optional[str]]:
    """
    List sessions with new SK pattern.

    Key improvements:
    - No in-memory filtering (S#ACTIVE# only matches sessions)
    - No in-memory sorting (SK includes timestamp)
    - True server-side pagination
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    query_params = {
        'KeyConditionExpression': Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('S#ACTIVE#'),
        'ScanIndexForward': False  # Descending (most recent first)
    }

    if limit:
        query_params['Limit'] = limit

    if next_token:
        query_params['ExclusiveStartKey'] = json.loads(
            base64.b64decode(next_token).decode('utf-8')
        )

    response = table.query(**query_params)

    sessions = []
    for item in response.get('Items', []):
        item = _convert_decimal_to_float(item)
        # Remove DynamoDB keys
        for key in ['PK', 'SK', 'GSI_PK', 'GSI_SK']:
            item.pop(key, None)
        sessions.append(SessionMetadata.model_validate(item))

    # Generate next_token from LastEvaluatedKey
    next_page_token = None
    if 'LastEvaluatedKey' in response:
        next_page_token = base64.b64encode(
            json.dumps(response['LastEvaluatedKey']).encode('utf-8')
        ).decode('utf-8')

    return sessions, next_page_token
```

### Session Service for Delete

```python
# backend/src/apis/app_api/sessions/services/session_service.py

class SessionService:
    """Service for session CRUD operations."""

    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table_name = os.environ.get('DYNAMODB_SESSIONS_METADATA_TABLE_NAME', 'SessionsMetadata')
        self.table = self.dynamodb.Table(self.table_name)

    async def get_session(self, user_id: str, session_id: str) -> Optional[SessionMetadata]:
        """Get session by ID using GSI."""
        response = self.table.query(
            IndexName='SessionLookupIndex',
            KeyConditionExpression=Key('GSI_PK').eq(f'SESSION#{session_id}') & Key('GSI_SK').eq('META')
        )

        items = response.get('Items', [])
        if not items:
            return None

        item = _convert_decimal_to_float(items[0])

        # Verify user ownership
        if item.get('userId') != user_id:
            return None

        # Remove DynamoDB keys
        for key in ['PK', 'SK', 'GSI_PK', 'GSI_SK']:
            item.pop(key, None)

        return SessionMetadata.model_validate(item)

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """
        Soft-delete a session.

        Moves from S#ACTIVE# to S#DELETED# prefix.
        Deletes conversation content from AgentCore Memory.
        Preserves cost records (C# prefix).
        """
        session = await self.get_session(user_id, session_id)
        if not session:
            return False

        if session.deleted:
            return True  # Already deleted

        now = datetime.now(timezone.utc)

        old_sk = f'S#ACTIVE#{session.last_message_at}#{session_id}'
        new_sk = f'S#DELETED#{now.isoformat()}#{session_id}'

        # Build deleted item
        deleted_item = {
            'PK': {'S': f'USER#{user_id}'},
            'SK': {'S': new_sk},
            'GSI_PK': {'S': f'SESSION#{session_id}'},
            'GSI_SK': {'S': 'META'},
            'sessionId': {'S': session_id},
            'userId': {'S': user_id},
            'title': {'S': session.title or ''},
            'status': {'S': 'deleted'},
            'createdAt': {'S': session.created_at},
            'lastMessageAt': {'S': session.last_message_at},
            'messageCount': {'N': str(session.message_count or 0)},
            'deleted': {'BOOL': True},
            'deletedAt': {'S': now.isoformat()}
        }

        # Transactional move
        self.dynamodb.meta.client.transact_write_items(
            TransactItems=[
                {
                    'Delete': {
                        'TableName': self.table_name,
                        'Key': {
                            'PK': {'S': f'USER#{user_id}'},
                            'SK': {'S': old_sk}
                        }
                    }
                },
                {
                    'Put': {
                        'TableName': self.table_name,
                        'Item': deleted_item
                    }
                }
            ]
        )

        # Delete conversation content from AgentCore Memory
        await self._delete_agentcore_memory(session_id)

        return True

    async def _delete_agentcore_memory(self, session_id: str) -> None:
        """Delete conversation content from AgentCore Memory."""
        # Implementation depends on AgentCore Memory API
        pass
```

---

## API Changes

### New Endpoint: Delete Session

```python
# backend/src/apis/app_api/sessions/routes.py

@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation.

    This soft-deletes the session metadata and permanently deletes
    the conversation content from AgentCore Memory.

    Cost records are preserved for billing and audit purposes.

    Args:
        session_id: Session identifier
        current_user: Authenticated user

    Returns:
        204 No Content on success

    Raises:
        404: Session not found
    """
    service = SessionService()
    deleted = await service.delete_session(
        user_id=current_user.user_id,
        session_id=session_id
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return Response(status_code=204)
```

### Frontend Service Update

```typescript
// frontend/ai.client/src/app/session/services/session/session.service.ts

@Injectable({ providedIn: 'root' })
export class SessionService {
  private http = inject(HttpClient);

  /**
   * Delete a conversation.
   *
   * This removes the conversation from the user's list and deletes
   * the message content. Cost records are preserved.
   */
  deleteSession(sessionId: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/sessions/${sessionId}`);
  }
}
```

### Frontend Component Update

```typescript
@Component({
  selector: 'app-session-list-item',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  providers: [provideIcons({ heroTrash })],
  template: `
    <div class="session-item">
      <span>{{ session().title }}</span>

      <button
        (click)="onDelete($event)"
        class="text-red-500 hover:text-red-700"
        aria-label="Delete conversation"
      >
        <ng-icon name="heroTrash" class="size-5" />
      </button>
    </div>

    @if (showConfirmDialog()) {
      <app-confirm-dialog
        title="Delete Conversation"
        message="Are you sure you want to delete this conversation? This action cannot be undone."
        (confirmed)="confirmDelete()"
        (cancelled)="showConfirmDialog.set(false)"
      />
    }
  `
})
export class SessionListItemComponent {
  session = input.required<SessionMetadata>();
  deleted = output<string>();

  private sessionService = inject(SessionService);

  showConfirmDialog = signal(false);
  isDeleting = signal(false);

  onDelete(event: Event) {
    event.stopPropagation();
    this.showConfirmDialog.set(true);
  }

  confirmDelete() {
    this.isDeleting.set(true);

    this.sessionService.deleteSession(this.session().sessionId)
      .pipe(finalize(() => {
        this.isDeleting.set(false);
        this.showConfirmDialog.set(false);
      }))
      .subscribe({
        next: () => this.deleted.emit(this.session().sessionId),
        error: (err) => console.error('Failed to delete session:', err)
      });
  }
}
```

---

## Testing Strategy

### Unit Tests

```python
class TestSessionService:

    async def test_list_sessions_returns_only_active(self, mock_dynamodb):
        """Listing sessions should not include deleted sessions."""
        service = SessionService()

        # Create active and deleted sessions
        await create_session_with_sk("S#ACTIVE#2025-01-15T10:00:00Z#session1", ...)
        await create_session_with_sk("S#DELETED#2025-01-15T11:00:00Z#session2", ...)

        sessions, _ = await service.list_sessions(user_id="alice")

        assert len(sessions) == 1
        assert sessions[0].session_id == "session1"

    async def test_delete_session_preserves_cost_records(self, mock_dynamodb):
        """Deleting a session should not affect cost records (C# prefix)."""
        # Create session and cost records
        await create_session_with_sk("S#ACTIVE#...", ...)
        await create_cost_record("C#2025-01-15T10:00:00Z#uuid1", session_id="abc")
        await create_cost_record("C#2025-01-15T10:01:00Z#uuid2", session_id="abc")

        # Delete session
        await service.delete_session(user_id="alice", session_id="abc")

        # Cost records should still exist
        costs = await get_costs_for_session("abc")
        assert len(costs) == 2

    async def test_list_sessions_no_longer_returns_cost_records(self, mock_dynamodb):
        """Cost records (C# prefix) should never appear in session listing."""
        # Create session and many cost records
        await create_session_with_sk("S#ACTIVE#...", ...)
        for i in range(100):
            await create_cost_record(f"C#2025-01-15T10:{i:02d}:00Z#uuid{i}", ...)

        sessions, _ = await service.list_sessions(user_id="alice", limit=20)

        # Should only get the 1 session, not cost records
        assert len(sessions) == 1
```

### Performance Tests

```python
async def test_list_sessions_performance_with_many_costs(self, mock_dynamodb):
    """
    Verify O(page_size) performance even with many cost records.

    Old implementation: O(sessions + messages) with in-memory filtering
    New implementation: O(page_size) direct query
    """
    # Create 100 sessions with 100 cost records each = 10,000 total records
    for i in range(100):
        await create_session_with_sk(f"S#ACTIVE#...", session_id=f"session{i}")
        for j in range(100):
            await create_cost_record(f"C#...", session_id=f"session{i}")

    # Time the list operation
    start = time.time()
    sessions, _ = await service.list_sessions(user_id="alice", limit=20)
    elapsed = time.time() - start

    assert len(sessions) == 20
    assert elapsed < 0.1  # Should be <100ms
```

---

## Rollback Plan

Since this is pre-production, rollback is straightforward:

1. **Revert code changes** via git
2. **Remove GSI** (optional - GSI doesn't break old code)
3. Old SK patterns continue to work

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Session listing latency | <100ms p99 | CloudWatch metrics |
| Session deletion latency | <500ms p99 | CloudWatch metrics |
| Cost accuracy after deletion | 100% | Automated tests |
| Quota accuracy after deletion | 100% | Automated tests |
| Zero data loss during deletion | 100% | Cost record comparison |

---

## Open Questions

### 1. Hard Delete vs Soft Delete Only

**Current Decision**: Soft delete only (move to `S#DELETED#` prefix)

**Recommendation**: Implement soft delete first. Add scheduled hard delete in future if storage costs become significant.

### 2. Bulk Delete

**Question**: Should users be able to delete multiple sessions at once?

**Recommendation**: Phase 2 feature. Single delete first, then add bulk delete endpoint.

### 3. Admin Restore Capability

**Question**: Should admins be able to restore deleted sessions?

**Recommendation**: Session metadata can be restored (move from `S#DELETED#` to `S#ACTIVE#`), but AgentCore Memory content cannot be recovered. Document this limitation.

---

## Summary: SK Pattern Changes

| Record Type | Old SK Pattern | New SK Pattern |
|-------------|----------------|----------------|
| Active session | `SESSION#{session_id}` | `S#ACTIVE#{last_message_at}#{session_id}` |
| Deleted session | N/A | `S#DELETED#{deleted_at}#{session_id}` |
| Message cost | `SESSION#{session_id}#MSG#{message_id}` | `C#{timestamp}#{uuid}` |

**Key Benefits:**
- Clean prefix separation enables efficient queries
- Timestamp in session SK enables server-side sorted pagination
- Single table = simpler operations
- No new tables to create or manage
- TTL only affects cost records (sessions don't have `ttl` attribute)

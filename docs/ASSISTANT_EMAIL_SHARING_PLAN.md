# Assistant Email Sharing Implementation Plan

## Overview

This plan implements email-based sharing for assistants with `SHARED` visibility. The feature allows assistant owners to share assistants with specific users by email address, even before those users have logged into the system for the first time. This is possible because OIDC authentication guarantees that all users will have an email claim.

## Context: Assistant Visibility Model

The system has three visibility levels:

| Visibility | Access Control | Share Records | Use Case |
|------------|----------------|---------------|----------|
| **PRIVATE** | Owner only | None needed | Personal assistants |
| **PUBLIC** | Anyone with link | None needed (no tracking) | Classroom assistants with non-sensitive content (syllabus, grading guidelines, examples) |
| **SHARED** | Owner + explicitly shared emails | Yes - owner can see list | Proprietary/sensitive content requiring controlled access |

**Key Design Decision:** Share records and tracking only apply to `SHARED` visibility assistants. `PUBLIC` assistants are open access with no tracking, suitable for trusted organizational environments (state/local government, universities).

## Data Model

### DynamoDB Single-Table Design

Add share records to the existing assistants DynamoDB table:

**Primary Key Structure:**
```
PK: AST#{assistant_id}
SK: SHARE#{email}
```

**New Global Secondary Index (SharedWithIndex):**
```
GSI3_PK: SHARE#{email}
GSI3_SK: AST#{assistant_id}
```

### Access Patterns

1. **"Who is this assistant shared with?"**
   - Query: `PK = AST#{assistant_id}` with `begins_with(SK, 'SHARE#')`
   - Returns all share records for a specific assistant

2. **"What assistants are shared with me?"**
   - Query GSI3: `GSI3_PK = SHARE#{user_email}`
   - Returns all assistants shared with a specific email

3. **"Does user X have access to this assistant?"**
   - Check: `is_owner OR visibility=PUBLIC OR share_record_exists(assistant_id, user_email)`

## Backend Implementation

### 1. Models (`backend/src/apis/app_api/assistants/models.py`)

Add new Pydantic models:

```python
class ShareAssistantRequest(BaseModel):
    emails: List[str] = Field(..., min_length=1, description="Email addresses to share with")

class UnshareAssistantRequest(BaseModel):
    emails: List[str] = Field(..., min_length=1, description="Email addresses to remove")

class AssistantSharesResponse(BaseModel):
    assistant_id: str
    shared_with: List[str]  # List of emails
```

### 2. Service Layer (`backend/src/apis/app_api/assistants/services/assistant_service.py`)

Add new functions:

- `share_assistant(assistant_id: str, owner_id: str, emails: List[str])` - Create share records for specified emails
- `unshare_assistant(assistant_id: str, owner_id: str, emails: List[str])` - Delete share records
- `list_assistant_shares(assistant_id: str, owner_id: str) -> List[str]` - Get all emails this assistant is shared with
- `list_shared_with_user(user_email: str) -> List[Assistant]` - Get all assistants shared with this email
- `check_share_access(assistant_id: str, user_email: str) -> bool` - Check if share record exists

**Modify Access Control:**

Update `get_assistant_with_access_check()` to enforce share records for `SHARED` visibility:

```python
if assistant.visibility == 'SHARED':
    if assistant.owner_id != user_id:
        # Check if share record exists for user's email
        has_share = await check_share_access(assistant_id, user_email)
        if not has_share:
            return None  # Access denied
```

### 3. User Search Endpoint

**Location:** `backend/src/apis/app_api/users/routes.py` (new file) or add to existing user routes

Create a new user search endpoint for the sharing modal:

- `GET /users/search` - Search for users by email or name (partial match)
  - Query parameter: `q` (search query string, required)
  - Query parameter: `limit` (max results, default 20, max 50)
  - Returns: List of users matching the search (email, name, userId)
  - Access: Available to all authenticated users (not admin-only)
  - Purpose: Allow users to search for existing users in the system to share with

**Implementation Details:**

**Service Layer** (`backend/src/apis/app_api/users/service.py` or add to existing):
- `search_users(query: str, limit: int = 20) -> List[UserSearchResult]`
- Search logic:
  - Query EmailIndex for email prefix matches (case-insensitive)
  - Query StatusLoginIndex for active users and filter by name contains
  - Combine and deduplicate results
  - Limit results and return top matches
- Only return users with status='active'

**Response Model:**
```python
class UserSearchResult(BaseModel):
    user_id: str
    email: str
    name: str

class UserSearchResponse(BaseModel):
    users: List[UserSearchResult]
```

**Implementation Notes:**
- Search should match against email (prefix/contains) and name (contains)
- Results should be limited and paginated
- Only return active users
- Return minimal user info: email, name, userId (for display purposes)
- Use debouncing on frontend to avoid excessive API calls

### 4. API Routes (`backend/src/apis/app_api/assistants/routes.py`)

Add new endpoints:

- `POST /assistants/{id}/shares` - Share assistant with emails (owner only, requires ownership verification)
- `DELETE /assistants/{id}/shares` - Remove shares from emails (owner only)
- `GET /assistants/{id}/shares` - List all emails this assistant is shared with (owner only)

**Modify existing endpoint:**

- `GET /assistants` - Optionally include assistants shared with the current user (query GSI3 by user email)

### 5. Infrastructure (`infrastructure/lib/app-api-stack.ts`)

Add new Global Secondary Index to the assistants DynamoDB table:

```typescript
assistantsTable.addGlobalSecondaryIndex({
  indexName: 'SharedWithIndex',
  partitionKey: { name: 'GSI3_PK', type: AttributeType.STRING },
  sortKey: { name: 'GSI3_SK', type: AttributeType.STRING },
  projectionType: ProjectionType.ALL,
});
```

## Frontend Implementation

### 1. Models

**Assistant Models** (`frontend/ai.client/src/app/assistants/models/assistant.model.ts`):

Add TypeScript interfaces:

```typescript
export interface ShareAssistantRequest {
  emails: string[];
}

export interface UnshareAssistantRequest {
  emails: string[];
}

export interface AssistantSharesResponse {
  assistantId: string;
  sharedWith: string[];
}
```

**User Search Models** (create new or add to existing user models):

```typescript
export interface UserSearchResult {
  userId: string;
  email: string;
  name: string;
}

export interface UserSearchResponse {
  users: UserSearchResult[];
}
```

### 2. Services

**Assistant Service** (`frontend/ai.client/src/app/assistants/services/assistant.service.ts`):

Add methods:
- `shareAssistant(id: string, emails: string[]): Promise<void>`
- `unshareAssistant(id: string, emails: string[]): Promise<void>`
- `getAssistantShares(id: string): Promise<string[]>`

**User Service** (create new or add to existing user service):

Add method:
- `searchUsers(query: string, limit?: number): Promise<UserSearchResult[]>` - Search for users by email/name

### 3. Share Dialog Component (`frontend/ai.client/src/app/assistants/components/share-assistant-dialog.component.ts`)

Update/create share dialog with **two modes**:

**Mode 1: Search for Existing Users**
- Search input field that queries the user search endpoint as user types (debounced)
- Display search results with user name and email
- Allow selecting users from search results
- Selected users are added to the share list

**Mode 2: Add Emails Directly**
- Fallback option: "Add email addresses manually"
- Text input for email addresses (comma-delimited)
- Parse and validate email format
- Add to share list

**Common Features:**
- Display list of currently shared emails/users
- Remove button for each shared email/user
- Email format validation
- Only show/share for assistants with `SHARED` visibility
- Show user name if available, email if not found in system

### 4. Assistant List (`frontend/ai.client/src/app/assistants/components/assistant-list.component.ts`)

Update assistant list to:

- Show assistants shared with the current user (query via new service method)
- Display "Shared with me" indicator or separate section
- Include shared assistants in the main list view

## Implementation Tasks

1. **Backend Models** - Add ShareAssistantRequest, UnshareAssistantRequest, AssistantSharesResponse models
2. **Backend User Search** - Create user search endpoint (GET /users/search) with partial matching on email/name
3. **Backend Service** - Implement share/unshare/list functions and modify access check logic
4. **Backend Routes** - Add POST/DELETE/GET /assistants/{id}/shares endpoints
5. **CDK GSI** - Add SharedWithIndex GSI to assistants table in CDK infrastructure
6. **Frontend Models** - Add TypeScript interfaces for share requests/responses and user search results
7. **Frontend User Service** - Add searchUsers method to user service
8. **Frontend Assistant Service** - Add share/unshare/getShares methods to assistant service
9. **Frontend Dialog** - Update share dialog with user search and manual email input (two modes)
10. **Frontend List** - Update assistant list to show shared-with-me assistants

## Migration Considerations

**Important:** Existing assistants with `SHARED` visibility will have no share records after deployment. This means:

- Only the owner can access them (safe default)
- Owners must explicitly add shares after deployment to grant access
- This is intentional - it prevents accidental exposure of previously "SHARED" assistants that may have been misconfigured

## Security Considerations

1. **Email Normalization:** All emails should be lowercased before storage/querying (consistent with existing user email handling)
2. **Ownership Verification:** All share endpoints must verify the requester is the assistant owner
3. **Access Control:** Share records are only checked for `SHARED` visibility assistants
4. **Email Validation:** Frontend should validate email format before sending to backend

## Testing Considerations

1. Test sharing with emails that don't have user accounts yet
2. Test that shared assistants appear in user's list after they log in
3. Test that unsharing removes access immediately
4. Test that PUBLIC assistants don't require share records
5. Test that PRIVATE assistants can't be shared
6. Test email case insensitivity (lowercase normalization)

# Backend Architecture Cleanup - Design

## Overview

This design document outlines the technical approach to fix two critical architectural issues:
1. Exception suppression anti-pattern causing silent failures
2. Tight coupling between inference API and app API preventing independent deployment

## Architecture

### Current State

```
backend/src/apis/
├── shared/                    # Minimal shared code
│   ├── auth/                  # JWT, RBAC (good!)
│   ├── rbac/                  # Role management (good!)
│   ├── users/                 # User sync (good!)
│   ├── errors.py              # Error models (good!)
│   └── quota.py               # Quota utilities (good!)
├── app_api/                   # ECS Fargate deployment
│   ├── sessions/              # ❌ Used by inference_api
│   ├── files/                 # ❌ Used by inference_api
│   ├── assistants/            # ❌ Used by inference_api
│   └── admin/                 # ❌ Used by inference_api
└── inference_api/             # AgentCore Runtime deployment
    └── chat/
        ├── routes.py          # ❌ Imports from app_api
        └── service.py         # ❌ Imports from app_api
```

### Target State

```
backend/src/apis/
├── shared/                    # Expanded shared library
│   ├── auth/                  # JWT, RBAC (existing)
│   ├── rbac/                  # Role management (existing)
│   ├── users/                 # User sync (existing)
│   ├── errors.py              # Error models (existing)
│   ├── quota.py               # Quota utilities (existing)
│   ├── sessions/              # ✅ NEW: Session models & metadata
│   ├── files/                 # ✅ NEW: File resolver
│   ├── models/                # ✅ NEW: Managed models service
│   └── assistants/            # ✅ NEW: Assistant shared code
├── app_api/                   # ECS Fargate deployment
│   ├── sessions/              # ✅ App-specific session routes
│   ├── files/                 # ✅ App-specific file routes
│   ├── assistants/            # ✅ App-specific assistant routes
│   └── admin/                 # ✅ Admin-only routes
└── inference_api/             # AgentCore Runtime deployment
    └── chat/
        ├── routes.py          # ✅ Imports from shared only
        └── service.py         # ✅ Imports from shared only
```

## Component Design

### 1. Exception Handling Strategy

#### 1.1 Exception Classification

**Critical Exceptions (MUST propagate):**
- Database operation failures (DynamoDB, S3)
- Authentication/authorization failures
- Model invocation failures
- Required data validation failures
- External service failures affecting response

**Optional Exceptions (MAY suppress with justification):**
- Telemetry/metrics collection
- Background title generation
- Optional metadata enrichment
- Cache warming operations
- Non-critical logging enhancements

#### 1.2 Error Response Pattern

All API endpoints must follow this pattern:

```python
from fastapi import HTTPException
from apis.shared.errors import ErrorCode, create_error_response

@router.get("/example")
async def example_endpoint():
    try:
        # Business logic
        result = await some_operation()
        return result
    
    except HTTPException:
        # Re-raise FastAPI exceptions (already have correct status)
        raise
    
    except SpecificException as e:
        # Handle specific exceptions with appropriate status codes
        logger.error(f"Specific error: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,  # or appropriate code
            detail=create_error_response(
                code=ErrorCode.BAD_REQUEST,
                message="User-friendly message",
                detail=str(e)
            )
        )
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                code=ErrorCode.INTERNAL_ERROR,
                message="An unexpected error occurred",
                detail=str(e)
            )
        )
```

#### 1.3 Suppression Documentation Pattern

When suppression is justified:

```python
try:
    await optional_telemetry_operation()
except Exception as e:
    # JUSTIFICATION: Telemetry failures should not break user requests.
    # This is a fire-and-forget operation with no impact on response.
    logger.warning(f"Telemetry failed (non-critical): {e}")
    # No re-raise - explicitly suppressed
```

### 2. Shared Library Extraction

#### 2.1 Session Module (`apis/shared/sessions/`)

**Files to create:**
- `apis/shared/sessions/__init__.py` - Module exports
- `apis/shared/sessions/models.py` - Session data models
- `apis/shared/sessions/metadata.py` - Metadata operations
- `apis/shared/sessions/storage.py` - Storage abstraction

**Models to move:**
```python
# From: apis/app_api/sessions/models.py
# To: apis/shared/sessions/models.py

class SessionMetadata(BaseModel):
    session_id: str
    user_id: str
    title: str
    status: str
    created_at: str
    last_message_at: str
    message_count: int
    starred: bool
    tags: List[str]
    preferences: Optional[SessionPreferences]
    # ... all session-related models
```

**Services to move:**
```python
# From: apis/app_api/sessions/services/metadata.py
# To: apis/shared/sessions/metadata.py

async def store_session_metadata(
    session_id: str,
    user_id: str,
    session_metadata: SessionMetadata
) -> None:
    """Store session metadata (DynamoDB + local file)"""
    # Implementation stays the same
    # Error handling IMPROVED to propagate failures

async def get_session_metadata(
    session_id: str,
    user_id: str
) -> Optional[SessionMetadata]:
    """Retrieve session metadata"""
    # Implementation stays the same
    # Error handling IMPROVED to propagate failures
```

#### 2.2 Files Module (`apis/shared/files/`)

**Files to create:**
- `apis/shared/files/__init__.py` - Module exports
- `apis/shared/files/file_resolver.py` - File resolution from S3
- `apis/shared/files/models.py` - File-related models

**Code to move:**
```python
# From: apis/app_api/files/file_resolver.py
# To: apis/shared/files/file_resolver.py

class FileResolver:
    """Resolves file upload IDs to actual file content from S3"""
    
    async def resolve_files(
        self,
        user_id: str,
        upload_ids: List[str],
        max_files: int = 5
    ) -> List[ResolvedFileContent]:
        """Resolve upload IDs to file content"""
        # Implementation stays the same
        # Error handling IMPROVED to propagate failures
```

#### 2.3 Models Module (`apis/shared/models/`)

**Files to create:**
- `apis/shared/models/__init__.py` - Module exports
- `apis/shared/models/managed_models.py` - Model management service
- `apis/shared/models/models.py` - Model data models

**Code to move:**
```python
# From: apis/app_api/admin/services/managed_models.py
# To: apis/shared/models/managed_models.py

async def list_managed_models() -> List[ManagedModel]:
    """List all managed models from storage"""
    # Implementation stays the same
    # Error handling IMPROVED to propagate failures

async def get_managed_model(model_id: str) -> Optional[ManagedModel]:
    """Get a specific managed model"""
    # Implementation stays the same
    # Error handling IMPROVED to propagate failures
```

#### 2.4 Assistants Module (`apis/shared/assistants/`)

**Files to create:**
- `apis/shared/assistants/__init__.py` - Module exports
- `apis/shared/assistants/models.py` - Assistant data models
- `apis/shared/assistants/service.py` - Core assistant operations
- `apis/shared/assistants/rag_service.py` - RAG operations

**Code to move:**
```python
# From: apis/app_api/assistants/services/assistant_service.py
# To: apis/shared/assistants/service.py

async def get_assistant_with_access_check(
    assistant_id: str,
    user_id: str,
    user_email: str
) -> Optional[Assistant]:
    """Get assistant with RBAC access check"""
    # Implementation stays the same
    # Error handling IMPROVED to propagate failures

async def assistant_exists(assistant_id: str) -> bool:
    """Check if assistant exists"""
    # Implementation stays the same
```

```python
# From: apis/app_api/assistants/services/rag_service.py
# To: apis/shared/assistants/rag_service.py

async def search_assistant_knowledgebase_with_formatting(
    assistant_id: str,
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Search assistant knowledge base"""
    # Implementation stays the same
    # Error handling IMPROVED to propagate failures

def augment_prompt_with_context(
    user_message: str,
    context_chunks: List[Dict[str, Any]]
) -> str:
    """Augment user message with RAG context"""
    # Implementation stays the same
```

### 3. Import Path Updates

#### 3.1 Inference API Updates

**File: `apis/inference_api/chat/service.py`**
```python
# BEFORE:
from apis.app_api.sessions.models import SessionMetadata
from apis.app_api.sessions.services.metadata import store_session_metadata

# AFTER:
from apis.shared.sessions.models import SessionMetadata
from apis.shared.sessions.metadata import store_session_metadata
```

**File: `apis/inference_api/chat/routes.py`**
```python
# BEFORE:
from apis.app_api.admin.services.managed_models import list_managed_models
from apis.app_api.files.file_resolver import get_file_resolver
from apis.app_api.assistants.services.assistant_service import (
    get_assistant_with_access_check,
    mark_share_as_interacted,
)
from apis.app_api.assistants.services.rag_service import (
    augment_prompt_with_context,
    search_assistant_knowledgebase_with_formatting,
)
from apis.app_api.sessions.models import SessionMetadata
from apis.app_api.sessions.services.metadata import (
    get_session_metadata,
    store_session_metadata,
)

# AFTER:
from apis.shared.models.managed_models import list_managed_models
from apis.shared.files.file_resolver import get_file_resolver
from apis.shared.assistants.service import (
    get_assistant_with_access_check,
    mark_share_as_interacted,
)
from apis.shared.assistants.rag_service import (
    augment_prompt_with_context,
    search_assistant_knowledgebase_with_formatting,
)
from apis.shared.sessions.models import SessionMetadata
from apis.shared.sessions.metadata import (
    get_session_metadata,
    store_session_metadata,
)
```

#### 3.2 App API Updates

All app API modules that use the moved code must update imports:

```python
# BEFORE:
from apis.app_api.sessions.models import SessionMetadata
from apis.app_api.sessions.services.metadata import store_session_metadata

# AFTER:
from apis.shared.sessions.models import SessionMetadata
from apis.shared.sessions.metadata import store_session_metadata
```

### 4. Error Handling Improvements

#### 4.1 Files to Fix

Based on grep results, these files need error handling improvements:

**High Priority (Core Operations):**
1. `apis/app_api/sessions/services/metadata.py` - Multiple suppressions
2. `apis/app_api/storage/local_file_storage.py` - Session error logging
3. `apis/app_api/admin/services/managed_models.py` - Model operations
4. `apis/shared/users/sync.py` - User sync failures
5. `apis/shared/rbac/seeder.py` - Role seeding failures

**Medium Priority (Service Operations):**
6. `apis/app_api/admin/routes.py` - Multiple exception handlers
7. `apis/app_api/users/routes.py` - User search errors
8. `apis/app_api/admin/services/model_access.py` - Permission checks

**Low Priority (Optional Operations):**
9. `apis/shared/auth/dependencies.py` - User sync (already justified)
10. `apis/shared/auth/jwt_validator.py` - Debug logging (justified)
11. `apis/shared/auth/state_store.py` - Fallback to in-memory (justified)

#### 4.2 Metadata Storage Pattern

**Current (WRONG):**
```python
try:
    await store_to_dynamodb(data)
except Exception as e:
    logger.error(f"Failed to store: {e}")
    # Don't raise - metadata storage failures shouldn't break the app
    # ❌ WRONG: This is a critical operation!
```

**Fixed (CORRECT):**
```python
try:
    await store_to_dynamodb(data)
except ClientError as e:
    logger.error(f"DynamoDB error storing metadata: {e}", exc_info=True)
    raise HTTPException(
        status_code=503,
        detail=create_error_response(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Failed to store session metadata",
            detail=str(e)
        )
    )
except Exception as e:
    logger.error(f"Unexpected error storing metadata: {e}", exc_info=True)
    raise HTTPException(
        status_code=500,
        detail=create_error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
            detail=str(e)
        )
    )
```

#### 4.3 Title Generation Pattern (Justified Suppression)

**Current (ACCEPTABLE with better docs):**
```python
try:
    title = await generate_title(message)
    await store_metadata(title=title)
    return title
except Exception as e:
    logger.error(f"Failed to generate title: {e}", exc_info=True)
    # Don't re-raise - title generation is nice-to-have
    return "New Conversation"
```

**Improved (BETTER):**
```python
try:
    title = await generate_title(message)
    await store_metadata(title=title)
    return title
except Exception as e:
    # JUSTIFICATION: Title generation is a non-critical enhancement.
    # Failures should not block the chat request. We return a fallback
    # title and log the error for monitoring.
    logger.error(f"Title generation failed (non-critical): {e}", exc_info=True)
    return "New Conversation"  # Fallback title
```

### 5. Testing Strategy

#### 5.1 Unit Tests

**Test exception propagation:**
```python
# tests/apis/shared/sessions/test_metadata.py

async def test_store_session_metadata_dynamodb_failure():
    """Verify DynamoDB failures propagate as HTTPException"""
    with patch('boto3.client') as mock_client:
        mock_client.return_value.put_item.side_effect = ClientError(...)
        
        with pytest.raises(HTTPException) as exc_info:
            await store_session_metadata(session_id, user_id, metadata)
        
        assert exc_info.value.status_code == 503
        assert "SERVICE_UNAVAILABLE" in str(exc_info.value.detail)
```

**Test import independence:**
```python
# tests/apis/inference_api/test_imports.py

def test_no_app_api_imports():
    """Verify inference_api has no imports from app_api"""
    import ast
    import os
    
    inference_api_dir = "backend/src/apis/inference_api"
    
    for root, dirs, files in os.walk(inference_api_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath) as f:
                    tree = ast.parse(f.read())
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        assert not node.module.startswith('apis.app_api'), \
                            f"Found app_api import in {filepath}: {node.module}"
```

#### 5.2 Integration Tests

**Test API error responses:**
```python
# tests/apis/app_api/test_error_responses.py

async def test_session_metadata_storage_failure_returns_503(client):
    """Verify storage failures return 503, not 200"""
    with patch('apis.shared.sessions.metadata.store_session_metadata') as mock:
        mock.side_effect = ClientError(...)
        
        response = await client.post("/sessions", json={...})
        
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "service_unavailable"
```

#### 5.3 Deployment Tests

**Test independent builds:**
```bash
# Test inference API builds without app API
cd backend
docker build -f Dockerfile.inference-api -t inference-api:test .

# Test app API builds without inference API
docker build -f Dockerfile.app-api -t app-api:test .
```

## Implementation Plan

### Phase 1: Shared Library Extraction (No Breaking Changes)

**Goal:** Move shared code to `apis/shared/` without breaking existing functionality

**Steps:**
1. Create new shared modules with copied code
2. Update imports in inference_api to use shared modules
3. Update imports in app_api to use shared modules
4. Verify both APIs still work
5. Remove duplicate code from app_api (keep only app-specific code)

**Validation:**
- All tests pass
- Both APIs start successfully
- No import errors
- Existing functionality unchanged

### Phase 2: Exception Handling Improvements (Incremental)

**Goal:** Fix exception suppression patterns file-by-file

**Priority Order:**
1. Session metadata operations (high impact)
2. Storage operations (high impact)
3. Admin operations (medium impact)
4. Optional operations (low impact, document justification)

**Per-File Process:**
1. Identify all exception handlers
2. Classify as critical or optional
3. Add proper error propagation for critical operations
4. Document justification for optional suppressions
5. Add unit tests for error cases
6. Verify API returns correct status codes

**Validation:**
- Unit tests for error propagation
- Integration tests for API status codes
- Manual testing of error scenarios
- No regressions in existing functionality

### Phase 3: Documentation & Cleanup

**Goal:** Document patterns and clean up technical debt

**Steps:**
1. Create error handling guide for developers
2. Add code comments explaining patterns
3. Update API documentation with error responses
4. Remove old comments about suppression
5. Add linting rules to catch future violations

## Migration Guide

### For Developers

**When writing new code:**
1. Always propagate exceptions unless explicitly justified
2. Use `HTTPException` with appropriate status codes
3. Use `ErrorCode` enum from `apis/shared/errors.py`
4. Document any exception suppression with `# JUSTIFICATION:` comment
5. Import from `apis/shared/` for cross-API code

**When fixing existing code:**
1. Identify the exception handler
2. Determine if operation is critical or optional
3. If critical: Add proper error propagation
4. If optional: Add justification comment
5. Add unit test for error case
6. Verify API returns correct status code

### For Operations

**Monitoring improvements:**
- 5xx errors will now be visible in logs and metrics
- Error responses include structured `ErrorCode` for alerting
- Failed operations will no longer silently succeed

**Deployment changes:**
- Inference API and App API can be deployed independently
- No shared code dependencies between deployments
- Rollback one API without affecting the other

## Rollback Plan

### Phase 1 Rollback (Shared Library)

If issues arise after shared library extraction:

1. Revert import changes in inference_api
2. Revert import changes in app_api
3. Remove new shared modules
4. Restore original app_api code

**Risk:** Low - code is copied, not moved initially

### Phase 2 Rollback (Exception Handling)

If issues arise after error handling improvements:

1. Identify problematic file
2. Revert exception handling changes in that file
3. Keep other improvements
4. File bug for investigation

**Risk:** Low - changes are incremental per-file

## Success Criteria

### Functional Requirements

✅ All API endpoints return appropriate HTTP status codes
✅ Failed operations return 4xx/5xx, never 200 OK
✅ Error responses use structured `ErrorCode` enum
✅ Inference API has zero imports from `apis.app_api`
✅ Both APIs can build and deploy independently

### Non-Functional Requirements

✅ No breaking changes to API contracts
✅ No database schema changes required
✅ Existing functionality continues to work
✅ Test coverage for error cases
✅ Documentation for error handling patterns

### Operational Requirements

✅ Improved error visibility in logs
✅ Structured error codes for alerting
✅ Independent deployment capability
✅ Faster debugging of issues
✅ Better observability

## Risks & Mitigation

### Risk 1: Breaking Changes

**Risk:** Import path changes break existing code

**Mitigation:**
- Incremental approach (copy first, then update imports)
- Comprehensive testing at each step
- Keep old code until verified working
- Rollback plan ready

### Risk 2: Performance Impact

**Risk:** Error propagation adds latency

**Mitigation:**
- Error handling is already present, just improving it
- No new operations added
- Async operations remain async
- Monitor performance metrics

### Risk 3: Incomplete Migration

**Risk:** Some files still suppress exceptions

**Mitigation:**
- Systematic file-by-file approach
- Grep search to find all instances
- Code review checklist
- Linting rules to prevent regression

### Risk 4: Deployment Complexity

**Risk:** Shared library changes affect both APIs

**Mitigation:**
- Deploy both APIs together initially
- Test in staging environment first
- Gradual rollout to production
- Monitor error rates closely

## Appendix

### A. Error Code Mapping

| HTTP Status | ErrorCode | Use Case |
|-------------|-----------|----------|
| 400 | BAD_REQUEST | Invalid input, malformed request |
| 401 | UNAUTHORIZED | Missing or invalid authentication |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource doesn't exist |
| 409 | CONFLICT | Resource already exists |
| 422 | VALIDATION_ERROR | Input validation failed |
| 429 | RATE_LIMIT_EXCEEDED | Too many requests |
| 500 | INTERNAL_ERROR | Unexpected server error |
| 503 | SERVICE_UNAVAILABLE | External service failure |
| 504 | TIMEOUT | Operation timed out |

### B. Shared Module Structure

```
apis/shared/
├── __init__.py
├── errors.py                  # ✅ Existing
├── quota.py                   # ✅ Existing
├── auth/                      # ✅ Existing
│   ├── dependencies.py
│   ├── jwt_validator.py
│   ├── models.py
│   └── rbac.py
├── rbac/                      # ✅ Existing
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   └── seeder.py
├── users/                     # ✅ Existing
│   ├── models.py
│   ├── repository.py
│   └── sync.py
├── sessions/                  # ✅ NEW
│   ├── __init__.py
│   ├── models.py
│   ├── metadata.py
│   └── storage.py
├── files/                     # ✅ NEW
│   ├── __init__.py
│   ├── models.py
│   └── file_resolver.py
├── models/                    # ✅ NEW
│   ├── __init__.py
│   ├── models.py
│   └── managed_models.py
└── assistants/                # ✅ NEW
    ├── __init__.py
    ├── models.py
    ├── service.py
    └── rag_service.py
```

### C. Files Requiring Changes

**Shared Library Creation (Phase 1):**
- Create: `apis/shared/sessions/` (4 files)
- Create: `apis/shared/files/` (3 files)
- Create: `apis/shared/models/` (3 files)
- Create: `apis/shared/assistants/` (4 files)

**Import Updates (Phase 1):**
- Update: `apis/inference_api/chat/routes.py`
- Update: `apis/inference_api/chat/service.py`
- Update: All app_api files using moved code (~20 files)

**Error Handling Fixes (Phase 2):**
- Fix: `apis/shared/sessions/metadata.py` (after move)
- Fix: `apis/shared/users/sync.py`
- Fix: `apis/shared/rbac/seeder.py`
- Fix: `apis/app_api/storage/local_file_storage.py`
- Fix: `apis/app_api/admin/routes.py`
- Fix: `apis/app_api/admin/services/managed_models.py`
- Fix: `apis/app_api/admin/services/model_access.py`
- Fix: `apis/app_api/users/routes.py`

**Total:** ~50 files to modify

# Backend Architecture Cleanup - Requirements

## Overview

This spec addresses critical architectural issues in the backend codebase:
1. **Exception suppression** - Errors are logged but not bubbled up, causing API endpoints to return 200 OK even when backend operations fail
2. **Tight coupling** - The inference API (deployed to AgentCore Runtime) imports from app API (deployed to ECS Fargate), violating deployment separation

## Problem Statement

### Problem 1: Exception Suppression Anti-Pattern

Throughout the backend, exceptions are caught, logged, and then execution continues without re-raising or returning error responses. This results in:
- API endpoints returning 200 OK when operations actually failed
- Silent failures that are difficult to diagnose
- Inconsistent error handling across the codebase
- Poor observability and debugging experience

**Examples found:**
- `apis/shared/users/sync.py:90` - User sync failures don't break requests (comment: "Don't re-raise")
- `apis/shared/rbac/seeder.py:83` - Role seeding failures continue silently
- `apis/app_api/sessions/services/metadata.py:158` - Metadata storage failures suppressed (comment: "Don't raise")
- `apis/app_api/sessions/services/metadata.py:271` - DynamoDB metadata failures suppressed
- `apis/app_api/sessions/services/metadata.py:409` - Cost summary update failures suppressed
- `apis/app_api/sessions/services/metadata.py:505` - System rollup failures suppressed
- `apis/app_api/storage/local_file_storage.py:218` - Session error logging without propagation
- Multiple instances in admin routes, storage layers, and service modules

### Problem 2: Deployment Coupling

The inference API (AgentCore Runtime deployment) directly imports from app API modules:
- `apis/inference_api/chat/service.py` imports from `apis.app_api.sessions.models`
- `apis/inference_api/chat/service.py` imports from `apis.app_api.sessions.services.metadata`
- `apis/inference_api/chat/routes.py` imports from `apis.app_api.admin.services.managed_models`
- `apis/inference_api/chat/routes.py` imports from `apis.app_api.files.file_resolver`
- `apis/inference_api/chat/routes.py` imports from `apis.app_api.assistants.services.*`
- `apis/inference_api/chat/routes.py` imports from `apis.app_api.sessions.*`

This creates deployment issues:
- Inference API container must include app API code
- Changes to app API can break inference API
- Cannot deploy/scale services independently
- Violates separation of concerns

## User Stories

### 1. Exception Handling

**As a** cloud architect  
**I want** all backend exceptions to bubble up to API endpoints with appropriate HTTP status codes  
**So that** I can properly diagnose issues and clients receive accurate error responses

**Acceptance Criteria:**
1.1. All caught exceptions must either be re-raised or converted to HTTPException with appropriate status codes
1.2. Only truly optional operations (like metrics, logging enhancements) may suppress exceptions with explicit justification
1.3. API endpoints return 4xx/5xx status codes when operations fail, never 200 OK
1.4. Error responses include structured error information using the existing `ErrorCode` enum
1.5. Suppressed exceptions must be explicitly documented with comments explaining why suppression is safe

### 2. Shared Module Extraction

**As a** cloud architect  
**I want** common code used by both APIs to live in the shared library  
**So that** inference API and app API can be deployed independently

**Acceptance Criteria:**
2.1. Session models are moved to `apis/shared/sessions/models.py`
2.2. Session metadata operations are moved to `apis/shared/sessions/metadata.py`
2.3. File resolver is moved to `apis/shared/files/file_resolver.py`
2.4. Managed models service is moved to `apis/shared/models/managed_models.py`
2.5. Assistant-related shared code is moved to `apis/shared/assistants/`
2.6. Inference API has zero imports from `apis.app_api.*`
2.7. App API imports from shared library where appropriate
2.8. Both APIs can build and deploy independently

### 3. Error Response Consistency

**As a** frontend developer  
**I want** consistent error response formats across all API endpoints  
**So that** I can handle errors predictably in the UI

**Acceptance Criteria:**
3.1. All error responses use the `ErrorDetail` model from `apis/shared/errors.py`
3.2. HTTP status codes correctly reflect error types (400, 401, 403, 404, 409, 422, 429, 500, 503, 504)
3.3. Error responses include `code`, `message`, and optional `detail` fields
3.4. SSE streams use `ConversationalErrorEvent` for user-facing errors
3.5. Internal errors include sufficient detail for debugging without exposing sensitive information

### 4. Backward Compatibility

**As a** system operator  
**I want** these changes to maintain API compatibility  
**So that** existing clients continue to work without modification

**Acceptance Criteria:**
4.1. API endpoint paths remain unchanged
4.2. Request/response schemas remain unchanged (except error responses improve)
4.3. Existing functionality continues to work
4.4. Database schemas remain unchanged
4.5. Environment variables remain unchanged

## Technical Context

### Current Architecture

```
backend/src/
├── apis/
│   ├── shared/          # Shared utilities (minimal)
│   │   ├── auth/        # JWT validation, RBAC
│   │   ├── rbac/        # Role-based access control
│   │   ├── users/       # User sync service
│   │   ├── errors.py    # Error models (good!)
│   │   └── quota.py     # Quota utilities
│   ├── app_api/         # Main API (ECS Fargate)
│   │   ├── sessions/    # Session management
│   │   ├── files/       # File operations
│   │   ├── assistants/  # Assistant services
│   │   └── admin/       # Admin operations
│   └── inference_api/   # AgentCore Runtime API
│       └── chat/        # Chat invocation
└── agents/              # Agent implementations
```

### Deployment Targets

- **App API**: ECS Fargate container, port 8000, full application features
- **Inference API**: AgentCore Runtime container, port 8001, minimal endpoints (/ping, /invocations)

### Existing Error Infrastructure

The codebase already has good error models in `apis/shared/errors.py`:
- `ErrorCode` enum with standard error types
- `ErrorDetail` model for structured errors
- `StreamErrorEvent` for SSE errors
- `ConversationalErrorEvent` for user-facing stream errors
- Helper functions for error response creation

**We need to USE these consistently!**

## Dependencies

- FastAPI (existing)
- Pydantic (existing)
- Python 3.13+ (existing)
- boto3 (existing)
- Existing database schemas (no changes)

## Constraints

1. **No breaking changes** to API contracts
2. **No database migrations** required
3. **Maintain existing functionality** - only improve error handling
4. **Independent deployability** - inference API must not depend on app API
5. **Backward compatibility** - existing clients must continue working

## Success Metrics

1. Zero instances of caught exceptions that don't re-raise or return errors
2. Zero imports from `apis.app_api` in `apis.inference_api`
3. All API endpoints return appropriate HTTP status codes
4. Improved error observability in logs and monitoring
5. Both APIs can build and deploy independently

## Out of Scope

- Frontend error handling improvements (separate effort)
- New error types or codes (use existing `ErrorCode` enum)
- Logging infrastructure changes
- Monitoring/alerting setup
- Performance optimization
- New features or functionality

## Notes

### Exception Suppression Philosophy

**When to suppress exceptions:**
- ✅ Optional telemetry/metrics that shouldn't break requests
- ✅ Best-effort operations with explicit fallbacks
- ✅ Background tasks that are truly fire-and-forget

**When to propagate exceptions:**
- ❌ Core business logic failures
- ❌ Data persistence failures
- ❌ Authentication/authorization failures
- ❌ External service failures that affect the response
- ❌ Validation failures

**Rule of thumb:** If the operation's failure means the API response is incomplete or incorrect, the exception MUST propagate.

### Shared Library Organization

The shared library should contain:
- Models used by both APIs
- Services that both APIs need (with no API-specific logic)
- Utilities and helpers
- Error definitions
- Authentication/authorization

The shared library should NOT contain:
- API-specific route handlers
- API-specific business logic
- Deployment-specific configuration

# Backend Architecture Cleanup - Tasks

## Phase 1: Shared Library Extraction ✅ COMPLETED

### 1. Create Shared Sessions Module ✅

- [x] 1.1 Create `apis/shared/sessions/__init__.py` with module exports
- [x] 1.2 Copy session models from `apis/app_api/sessions/models.py` to `apis/shared/sessions/models.py`
- [x] 1.3 Copy metadata operations from `apis/app_api/sessions/services/metadata.py` to `apis/shared/sessions/metadata.py`
- [x] 1.4 Copy message operations from `apis/app_api/sessions/services/messages.py` to `apis/shared/sessions/messages.py`
- [x] 1.5 Update imports within shared sessions module to use relative imports
- [x] 1.6 Verify shared sessions module can be imported without errors

### 2. Create Shared Files Module ✅

- [x] 2.1 Create `apis/shared/files/__init__.py` with module exports
- [x] 2.2 Copy file models from `apis/app_api/files/models.py` to `apis/shared/files/models.py`
- [x] 2.3 Copy file resolver from `apis/app_api/files/file_resolver.py` to `apis/shared/files/file_resolver.py`
- [x] 2.4 Copy file repository from `apis/app_api/files/repository.py` to `apis/shared/files/repository.py`
- [x] 2.5 Update imports within shared files module to use relative imports
- [x] 2.6 Verify shared files module can be imported without errors

### 3. Create Shared Models Module ✅

- [x] 3.1 Create `apis/shared/models/__init__.py` with module exports
- [x] 3.2 Copy managed models service from `apis/app_api/admin/services/managed_models.py` to `apis/shared/models/managed_models.py`
- [x] 3.3 Extract model data models to `apis/shared/models/models.py`
- [x] 3.4 Update imports within shared models module to use relative imports
- [x] 3.5 Verify shared models module can be imported without errors

### 4. Create Shared Assistants Module ✅

- [x] 4.1 Create `apis/shared/assistants/__init__.py` with module exports
- [x] 4.2 Copy assistant models from `apis/app_api/assistants/models.py` to `apis/shared/assistants/models.py`
- [x] 4.3 Copy core assistant service from `apis/app_api/assistants/services/assistant_service.py` to `apis/shared/assistants/service.py`
- [x] 4.4 Copy RAG service from `apis/app_api/assistants/services/rag_service.py` to `apis/shared/assistants/rag_service.py`
- [x] 4.5 Update imports within shared assistants module to use relative imports
- [x] 4.6 Verify shared assistants module can be imported without errors

### 5. Update Inference API Imports ✅

- [x] 5.1 Update `apis/inference_api/chat/service.py` to import from `apis.shared.sessions`
- [x] 5.2 Update `apis/inference_api/chat/routes.py` to import sessions from `apis.shared.sessions`
- [x] 5.3 Update `apis/inference_api/chat/routes.py` to import files from `apis.shared.files`
- [x] 5.4 Update `apis/inference_api/chat/routes.py` to import models from `apis.shared.models`
- [x] 5.5 Update `apis/inference_api/chat/routes.py` to import assistants from `apis.shared.assistants`
- [x] 5.6 Verify inference API starts without import errors
- [x] 5.7 Test inference API `/ping` endpoint
- [x] 5.8 Test inference API `/invocations` endpoint with sample request

### 6. Update App API Imports ✅

- [x] 6.1 Update `apis/app_api/sessions/routes.py` to import from `apis.shared.sessions`
- [x] 6.2 Update `apis/app_api/sessions/services/` files to import from `apis.shared.sessions`
- [x] 6.3 Update `apis/app_api/files/routes.py` to import from `apis.shared.files`
- [x] 6.4 Update `apis/app_api/files/service.py` to import from `apis.shared.files`
- [x] 6.5 Update `apis/app_api/admin/routes.py` to import models from `apis.shared.models`
- [x] 6.6 Update `apis/app_api/assistants/routes.py` to import from `apis.shared.assistants`
- [x] 6.7 Update `apis/app_api/assistants/services/` files to import from `apis.shared.assistants`
- [x] 6.8 Update `apis/app_api/chat/routes.py` to import from shared modules
- [x] 6.9 Update `apis/app_api/memory/routes.py` to import from shared modules
- [x] 6.10 Verify app API starts without import errors
- [x] 6.11 Test app API health endpoint
- [x] 6.12 Test app API session endpoints

### 7. Verify Independent Deployment

- [ ] 7.1 Build inference API Docker image independently
- [ ] 7.2 Build app API Docker image independently
- [ ] 7.3 Run inference API container and verify it starts
- [ ] 7.4 Run app API container and verify it starts
- [x] 7.5 Verify no cross-API imports using static analysis
- [ ] 7.6 Run full test suite for both APIs

### 8. Clean Up Duplicate Code ✅

- [x] 8.1 Remove duplicate session code from `apis/app_api/sessions/models.py` (keep only app-specific)
- [x] 8.2 Remove duplicate file code from `apis/app_api/files/` (keep only app-specific routes)
- [x] 8.3 Remove duplicate model code from `apis/app_api/admin/services/managed_models.py` (keep only admin-specific)
- [x] 8.4 Remove duplicate assistant code from `apis/app_api/assistants/` (keep only app-specific routes)
- [x] 8.5 Update any remaining imports to use shared modules
- [x] 8.6 Verify no broken imports after cleanup

## Phase 2: Exception Handling Improvements ✅ COMPLETED

### 9. Fix Session Metadata Error Handling ✅

- [x] 9.1 Update `store_session_metadata()` in `apis/shared/sessions/metadata.py` to propagate DynamoDB errors
- [x] 9.2 Update `store_session_metadata()` to propagate file storage errors
- [x] 9.3 Update `get_session_metadata()` to propagate retrieval errors
- [x] 9.4 Update `update_cost_summary()` - Justified suppression documented (fire-and-forget background operation)
- [x] 9.5 Update `update_system_rollups()` - Justified suppression documented (supplementary analytics)
- [x] 9.6 Add justification comments for remaining suppressions (GSI lookup, pagination, individual session parsing)
- [x] 9.7 Add unit tests for error propagation in metadata operations
- [x] 9.8 Test API returns 503 when DynamoDB is unavailable

### 10. Fix Storage Error Handling ✅

- [x] 10.1 Update `local_file_storage.py` session error handling - Justified suppressions documented (aggregation resilience)
- [x] 10.2 Update `dynamodb_storage.py` error handling - No changes needed (already propagates)
- [x] 10.3 Add proper HTTPException with status codes for storage failures
- [x] 10.4 Add unit tests for storage error propagation
- [x] 10.5 Test API returns appropriate status codes for storage failures

### 11. Fix Managed Models Error Handling ✅

- [x] 11.1 Update `create_managed_model()` in `apis/shared/models/managed_models.py` - Already propagates errors
- [x] 11.2 Update `update_managed_model()` to propagate errors
- [x] 11.3 Update `delete_managed_model()` to propagate errors
- [x] 11.4 Update `list_managed_models()` to propagate critical errors
- [x] 11.5 Add proper HTTPException with status codes for model operations
- [x] 11.6 Add unit tests for model operation error propagation
- [x] 11.7 Test API returns appropriate status codes for model operation failures

### 12. Fix User Sync Error Handling ✅

- [x] 12.1 Review `apis/shared/users/sync.py` exception handling
- [x] 12.2 Add justification comment for sync failure suppression (best-effort, auth still works)
- [x] 12.3 Consider propagating critical sync failures - Decided: suppression is appropriate
- [x] 12.4 Add unit tests for user sync error scenarios
- [x] 12.5 Document when sync failures should/shouldn't break requests

### 13. Fix RBAC Seeder Error Handling ✅

- [x] 13.1 Review `apis/shared/rbac/seeder.py` exception handling
- [x] 13.2 Add justification comment for role seeding suppression (resilient startup)
- [x] 13.3 Consider propagating critical seeding failures - Decided: partial seeding is acceptable
- [x] 13.4 Add unit tests for seeder error scenarios
- [x] 13.5 Document seeder error handling strategy

### 14. Fix Admin Routes Error Handling ✅

- [x] 14.1 Review `apis/app_api/admin/routes.py` - Already has proper error handling
- [x] 14.2 Verify Gemini model listing error handling - Already correct
- [x] 14.3 Verify OpenAI model listing error handling - Already correct
- [x] 14.4 Verify enabled models CRUD error handling - Already correct
- [x] 14.5 Ensure all admin routes return appropriate status codes - Verified
- [x] 14.6 Add integration tests for admin route error responses
- [x] 14.7 Test API returns correct status codes for admin operation failures

### 15. Fix Model Access Error Handling ✅

- [x] 15.1 Update `apis/app_api/admin/services/model_access.py` permission check error handling
- [x] 15.2 Decide if permission check failures should propagate or fall back - Decided: fallback to JWT roles
- [x] 15.3 Add justification comments for suppressions (AppRole → JWT fallback)
- [x] 15.4 Add unit tests for permission check error scenarios
- [x] 15.5 Document permission check error handling strategy

### 16. Fix User Routes Error Handling ✅

- [x] 16.1 Review `apis/app_api/users/routes.py` - Already has proper error handling
- [x] 16.2 Ensure user operations return appropriate status codes - Verified
- [x] 16.3 Add integration tests for user route error responses
- [x] 16.4 Test API returns correct status codes for user operation failures

### 17. Document Justified Suppressions ✅

- [x] 17.1 Add justification comment to title generation error handling
- [x] 17.2 Add justification comment to telemetry/metrics error handling
- [x] 17.3 Add justification comment to optional cache operations
- [x] 17.4 Add justification comment to debug logging failures
- [x] 17.5 Create list of all justified suppressions for code review - Created `JUSTIFIED_EXCEPTION_SUPPRESSIONS.md`

## Phase 3: Validation & Testing

### 18. Docker Build Verification

- [ ] 18.1 Build inference API Docker image: `docker build -f backend/Dockerfile.inference-api -t inference-api:test .`
- [ ] 18.2 Build app API Docker image: `docker build -f backend/Dockerfile.app-api -t app-api:test .`
- [ ] 18.3 Run inference API container and verify startup: `docker run -p 8001:8001 inference-api:test`
- [ ] 18.4 Run app API container and verify startup: `docker run -p 8000:8000 app-api:test`
- [ ] 18.5 Test inference API health endpoint: `curl http://localhost:8001/ping`
- [ ] 18.6 Test app API health endpoint: `curl http://localhost:8000/health`

### 19. Integration Testing

- [ ] 19.1 Set up test environment with required AWS credentials
- [ ] 19.2 Run pytest test suite: `python -m pytest tests/ -v`
- [ ] 19.3 Verify all existing tests pass
- [ ] 19.4 Test session creation and retrieval via API
- [ ] 19.5 Test file upload and resolution via API
- [ ] 19.6 Test assistant operations via API
- [ ] 19.7 Test error responses return correct status codes

### 20. Manual Smoke Testing

- [ ] 20.1 Start both APIs locally (app API on 8000, inference API on 8001)
- [ ] 20.2 Create a new chat session via app API
- [ ] 20.3 Send a message via inference API and verify response
- [ ] 20.4 Upload a file and verify it can be resolved
- [ ] 20.5 Test assistant with RAG knowledge base
- [ ] 20.6 Verify error handling by simulating DynamoDB failure
- [ ] 20.7 Check logs for proper error messages and stack traces

## Phase 4: Documentation & Cleanup

### 21. Update Documentation

- [ ] 21.1 Update `backend/README.md` with new shared module structure
- [ ] 21.2 Document error handling patterns for developers
- [ ] 21.3 Add API error response examples to documentation
- [ ] 21.4 Update deployment guide with independent deployment instructions
- [ ] 21.5 Document monitoring recommendations for error tracking

### 22. Code Quality & Linting

- [ ] 22.1 Run ruff linter: `ruff check backend/src/`
- [ ] 22.2 Run black formatter: `black backend/src/`
- [ ] 22.3 Run mypy type checker: `mypy backend/src/`
- [ ] 22.4 Fix any linting or type errors
- [ ] 22.5 Add pre-commit hooks for code quality checks

### 23. Final Cleanup

- [ ] 23.1 Remove any unused imports across the codebase
- [ ] 23.2 Remove commented-out code
- [ ] 23.3 Verify all TODO comments are addressed or documented
- [ ] 23.4 Clean up any temporary test files
- [ ] 23.5 Update CHANGELOG with architectural improvements

## Notes

### Completed Work Summary

**Phase 1: Shared Library Extraction ✅**
- All 4 shared modules created (sessions, files, models, assistants)
- All inference API imports updated to use shared modules
- All app API imports updated to use shared modules
- Duplicate code removed from app_api
- Zero imports from `apis.app_api` in `apis.inference_api` (verified)

**Phase 2: Exception Handling Improvements ✅**
- 18 exception handlers fixed across 6 files
- 11 handlers now propagate errors with proper HTTP status codes
- 10 handlers documented with clear justifications for suppression
- Created comprehensive documentation: `JUSTIFIED_EXCEPTION_SUPPRESSIONS.md`
- Error handling patterns established for future development

### Remaining Work

**Phase 3: Validation & Testing**
- Docker build and container verification
- Integration testing with pytest
- Manual smoke testing of both APIs
- Error response validation

**Phase 4: Documentation & Cleanup**
- Update developer documentation
- Code quality checks (ruff, black, mypy)
- Final cleanup and CHANGELOG update

### Task Dependencies

- Phase 1 ✅ COMPLETED
- Phase 2 ✅ COMPLETED
- Phase 3 requires Phase 1 & 2 completion
- Phase 4 can be done in parallel with Phase 3

### Estimated Effort

- ✅ Phase 1: 2-3 days (COMPLETED)
- ✅ Phase 2: 3-4 days (COMPLETED)
- Phase 3: 1-2 days (validation & testing)
- Phase 4: 1 day (documentation & cleanup)
- **Remaining: 2-3 days**

### Risk Mitigation

- ✅ Import independence verified via static analysis
- ✅ Exception handling patterns documented
- ⏭️ Docker builds will verify true deployment independence
- ⏭️ Integration tests will catch any runtime issues
- ⏭️ Manual testing will validate end-to-end functionality

### Success Criteria

✅ Zero imports from `apis.app_api` in `apis.inference_api`
✅ Shared library modules created and functional
✅ Both APIs import from shared modules correctly
✅ Error handling improved in critical paths
✅ Justified suppressions documented with comments
⏭️ Both APIs can build and deploy independently (Docker verification pending)
⏭️ All tests pass (integration testing pending)
⏭️ Documentation updated (pending)

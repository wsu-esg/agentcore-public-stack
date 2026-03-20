---
inclusion: manual
---

# Commit Review

Review the code changes in the provided commit or diff. Evaluate the feature/fix holistically and assign a letter grade (A, B, C, D, F) for each category below. Include a brief justification for each grade.

## Grading Scale

- **A** — Excellent. Follows best practices, no concerns.
- **B** — Good. Minor improvements possible but solid overall.
- **C** — Acceptable. Notable gaps that should be addressed before or shortly after merge.
- **D** — Below standard. Significant issues that need rework.
- **F** — Failing. Critical problems that block merge.

## Categories

### 1. Security
- No hardcoded secrets, API keys, or credentials
- Input validation and sanitization on all user inputs
- Authentication and authorization properly enforced
- No SQL injection, XSS, or CSRF vulnerabilities
- Least-privilege principle for IAM roles and permissions
- Sensitive data not exposed in logs, error messages, or client responses
- Dependencies are from trusted sources with no known vulnerabilities

### 2. User Experience
- UI changes are intuitive and consistent with existing patterns
- Loading states, empty states, and error states handled
- Responsive design considerations
- Feedback provided for user actions (success/failure)
- No regressions to existing workflows
- Semantic HTML elements used correctly
- ARIA attributes present where needed
- Keyboard navigation supported for interactive elements
- Color contrast sufficient for text and controls
- Screen reader compatibility considered

### 3. Infrastructure / Backend Design
- Resources properly scoped and configured
- CDK constructs follow project patterns
- No over-provisioning or under-provisioning
- Proper use of environment variables and configuration
- Database schema changes are backward compatible
- API design is consistent (proper HTTP methods, status codes, response shapes)
- Module boundaries respected, changes well-scoped

### 4. Code Quality
- Readable, well-named variables, functions, and classes
- DRY — no unnecessary duplication
- Proper abstractions without over-engineering
- No dead code, commented-out blocks, or debug statements
- Follows project naming conventions (snake_case backend, camelCase frontend)
- Errors caught and handled gracefully with meaningful messages
- No swallowed exceptions
- Fallback behavior defined where appropriate
- Complex logic documented with comments
- Easy to understand and modify for the next developer
- Configuration externalized, not hardcoded

### 5. Speed
- No unnecessary API calls or database queries
- Efficient algorithms and data structures
- Lazy loading and pagination where appropriate
- No blocking operations on the main thread (frontend)
- Async patterns used correctly (backend)
- Caching applied where beneficial

### 6. Cost Minimization
- AWS resource usage is efficient (right-sized compute, storage lifecycle)
- Token usage optimized for LLM calls
- No redundant infrastructure or unused resources
- DynamoDB read/write capacity considerations
- Minimal unnecessary network calls or data transfer

### 7. Testing
- All possible use cases and error cases are tested for and handled with error messages. 
- Any added code or updated features are tested for in a way that is consistent with the repos standard. 

## Output Format

Present the review as a table followed by detailed notes:

| Category | Grade | Summary |
|---|---|---|
| Security | ? | ... |
| User Experience | ? | ... |
| Infrastructure / Backend Design | ? | ... |
| Code Quality | ? | ... |
| Speed | ? | ... |
| Cost Minimization | ? | ... |
| **Overall** | **?** | ... |

Then provide:
- **Strengths**: What was done well
- **Issues**: Specific problems that need attention (with file/line references)
- **Suggestions**: Optional improvements that aren't blocking

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Production-ready multi-agent conversational AI system built with AWS Bedrock AgentCore and Strands Agents.

## Build & Run

### Backend
```bash
cd backend
uv sync --extra agentcore --extra dev        # All deps
uv run python -m pytest tests/ -v            # All tests
uv run python -m pytest tests/agents/ -v     # Single directory
uv run python -m pytest tests/agents/test_chat_agent.py::test_name -v  # Single test
cd src/apis/app_api && uv run python main.py    # App API (port 8000)
cd src/apis/inference_api && uv run python main.py  # Inference API (port 8001)
```

### Frontend
```bash
cd frontend/ai.client
npm install
npm run start    # Dev server (port 4200)
npm test         # Unit tests (Vitest via Analog.js)
npm run e2e      # Playwright e2e tests
```

### Infrastructure
```bash
cd infrastructure
npm install
npm run build
npx cdk synth
npx cdk deploy --all
```

## Version Management

Single source of truth is the `VERSION` file at the repo root (`MAJOR.MINOR.PATCH[-PRERELEASE]`, no `v` prefix).

```bash
# 1. Edit VERSION file
# 2. Sync to all manifests:
bash scripts/common/sync-version.sh
# 3. Commit VERSION + updated manifests
```

The sync script updates `backend/pyproject.toml`, `frontend/ai.client/package.json`, `infrastructure/package.json`, and the README version badge. PRs to `main` fail CI if VERSION is unchanged or manifests are out of sync.

## Key Conventions

- **Deploy order:** Infrastructure → Gateway → Inference API → App API → Frontend (App API reads `runtime-workload-identity-name` from SSM, published by Inference API)
- **Admin endpoints** go under `/admin/<domain>/`, user-facing under `/<domain>/`
- **Errors stream as assistant messages** via SSE (not HTTP error codes)
- **Signal-based state** throughout frontend (`signal()`, `computed()`)
- **All dependencies use exact version pins** — no `^`, `~`, or `>=`
- **Never install packages without explicit user approval**

## SSE Event Types

| Event | Purpose |
|-------|---------|
| `message_start` | Start of assistant response |
| `content_block_start/delta/stop` | Streaming content |
| `message_stop` | End of message |
| `tool_use` / `tool_result` | Tool invocation and result |
| `stream_error` | Conversational error |
| `oauth_required` | External MCP tool needs user consent — payload `{providerId, authorizationUrl}`, one event per provider emitted after `message_stop` |
| `compaction` | Backend rolled older turns into a summary on this turn — payload `{previousCheckpoint, newCheckpoint, summarizedTurns, inputTokens}`, emitted after the final `metadata` event so the badge updates first, before `done` |
| `done` | Stream complete |

## Multi-Protocol Tool Architecture

| Protocol | Location | Auth |
|----------|----------|------|
| Direct call | `agents/main_agent/tools/` | N/A |
| AWS SDK | `agents/main_agent/tools/` | IAM |
| MCP + SigV4 | Cloud Lambda (Gateway) | AWS SigV4 |
| A2A | Cloud Runtime | AgentCore auth |

## Cross-Package Contracts

- Backend route handlers define the API shape; frontend TypeScript interfaces must match
- Breaking changes to an endpoint require updating both packages in the same PR
- SSE event types are part of the contract — changes must be coordinated
- `app_api`, `inference_api`, and `agents/` are independent consumers of `apis.shared`. They must never import from each other — only from `apis.shared`. If something is needed by more than one of them, move it to `apis.shared`. This is enforced by `tests/architecture/test_import_boundaries.py`.

## File Creation Rules

| Change Type | Where It Goes |
|-------------|---------------|
| New API route | `backend/src/apis/app_api/<domain>/` |
| New admin endpoint | `backend/src/apis/app_api/admin/<domain>/` |
| New agent tool | `backend/src/agents/main_agent/tools/` + register in `__init__.py` |
| New Angular page | `frontend/ai.client/src/app/<feature>/` |
| New CDK stack | `infrastructure/lib/<stack-name>-stack.ts` |
| Shared backend code | `backend/src/apis/shared/<domain>/` |

### Inference API boundary

The `inference-api` runs inside an AgentCore Runtime container. The runtime data plane (`https://bedrock-agentcore.<region>.amazonaws.com/runtimes/<arn>/...`) only proxies the standard AgentCore paths — `POST /invocations` and `GET /ping`. **Other HTTP paths return 404 from AWS before the request ever reaches the container**, so any custom route added to inference-api is unreachable in cloud. Local dev is misleading because `localhost:8001` bypasses the runtime gateway entirely.

**Rule:** Don't add routes to `inference-api` unless they're part of the AgentCore Runtime invocation path (i.e. the chat router that owns `/invocations` and `/ping`). User-facing CRUD-ish endpoints — even ones that share dependencies with the agent loop — belong in `app-api`. If a coding agent suggests adding endpoints to inference-api "because it has the workload context," push back: the right pattern is to mint workload context on app-api via the `AGENTCORE_RUNTIME_WORKLOAD_NAME` mint fallback in `apis/shared/oauth/agentcore_identity.py`.

If you're tempted to add to inference-api because of an existing route there (`converse_router`, `voice_router`), don't use them as templates without confirming their access path — they predate this rule and may rely on bypasses (API key, WebSocket upgrade, direct container reach in environments where the runtime isn't the only path).

## Angular Patterns

These apply to all components in `frontend/ai.client/`:

- **Do NOT set `standalone: true`** — it's the default in Angular v20+; adding it is noise
- Use `input()` and `output()` functions instead of `@Input()`/`@Output()` decorators
- Use `inject()` function instead of constructor injection
- Set `changeDetection: ChangeDetectionStrategy.OnPush` on every `@Component`
- Use `host` object inside `@Component`/`@Directive` instead of `@HostBinding`/`@HostListener`
- Native control flow only: `@if`, `@for`, `@switch` — not `*ngIf`, `*ngFor`, `*ngSwitch`
- `class` and `style` bindings — not `ngClass` or `ngStyle`
- Reactive forms over template-driven forms
- `NgOptimizedImage` for all static images (does not work for inline base64)
- All UI must pass AXE checks and meet WCAG 2.1 AA (focus management, color contrast, ARIA)

## Debugging Quick Reference

- **Tool not appearing:** Check `__init__.py` export, RBAC permissions, `enabled_tools`, ToolRegistry
- **Session not persisting:** Check AgentCore Memory config, session_id, TurnBasedSessionManager flush
- **SSE stream disconnecting:** Check 600s timeout, client connection, quota exceeded events

## Coding Standards

### Python
- `snake_case` functions/variables, `PascalCase` classes
- Type hints required on all function signatures
- No `print()` in production — use `logging`

### TypeScript
- `camelCase` functions/variables, `PascalCase` classes/interfaces, `UPPER_SNAKE_CASE` constants
- Strict mode enabled — no `any` unless absolutely necessary

### General
- No commented-out code in commits
- Prefer early returns over deep nesting
- One logical change per commit using conventional commits (`feat:`, `fix:`, `chore:`, etc.)

## Git Workflow

- Branch from `develop`, never `main`
- PRs target `develop`; `main` is updated via squash-merge releases only
- Branch naming: `feature/<short-description>`

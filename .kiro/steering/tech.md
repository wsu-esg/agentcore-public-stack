# Technology Stack

## Frontend

- **Framework**: Angular v21 (standalone components)
- **Language**: TypeScript 5.9+
- **Styling**: Tailwind CSS v4.1+ (PostCSS)
- **UI Components**: Custom components with ng-icons (Heroicons)
- **Markdown**: ngx-markdown with KaTeX, Prism.js, Mermaid
- **Charts**: ng2-charts (Chart.js wrapper)
- **State Management**: Angular Signals (`signal()`, `computed()`)
- **Package Manager**: npm 11.2.0

## Backend

- **Language**: Python 3.13+
- **Framework**: FastAPI 0.116.1
- **Server**: Uvicorn 0.35.0 (ASGI)
- **Agent Framework**: Strands Agents 1.22.0
- **AWS SDK**: boto3 (Bedrock, S3, DynamoDB)
- **Authentication**: PyJWT with crypto support
- **Environment**: python-dotenv
- **Testing**: pytest, pytest-asyncio
- **Code Quality**: black, ruff, mypy

## Infrastructure

- **IaC**: AWS CDK (TypeScript)
- **Compute**: AWS Fargate (containerized)
- **CDN**: CloudFront
- **Load Balancer**: Application Load Balancer
- **Authentication**: AWS Cognito / Microsoft Entra ID
- **Storage**: S3, DynamoDB
- **AI Services**: AWS Bedrock (Claude, Nova Act)

## AWS Services

- **Bedrock AgentCore Runtime**: Containerized agent deployment
- **Bedrock AgentCore Memory**: Conversation persistence
- **Bedrock AgentCore Gateway**: MCP tool endpoints
- **Bedrock Code Interpreter**: Python code execution
- **Bedrock Browser**: Web automation with Nova Act
- **Lambda**: Gateway tool functions (5 functions, 12 tools)
- **DynamoDB**: User data, quotas, sessions, costs, RBAC
- **S3**: File uploads, static assets
- **S3 Vector Buckets**: RAG for assistant chats

## Development Tools

- **Version Control**: Git
- **Containerization**: Docker
- **Testing**: Vitest (frontend), pytest (backend)
- **Linting**: ESLint (frontend), ruff (backend)
- **Formatting**: Prettier (frontend), black (backend)
- **Type Checking**: TypeScript compiler, mypy

## Common Commands

### Setup & Installation

```bash
# Full project setup (one-time)
./setup.sh

# Start all services locally
./start.sh
```

### Backend Development

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[agentcore,dev]"  # All dependencies + dev tools
pip install -e ".[agentcore]"      # AgentCore + core dependencies
pip install -e "."                 # Core dependencies only

# Run App API (port 8000)
cd src/apis/app_api
python main.py

# Run Inference API (port 8001)
cd src/apis/inference_api
python main.py

# Run tests
python -m pytest tests/ -v

# Code formatting
black src/
ruff check src/

# Type checking
mypy src/
```

### Frontend Development

```bash
cd frontend/ai.client

# Install dependencies
npm install

# Development server (port 4200)
npm run start

# Production build
npm run build

# Run tests
npm test

# Watch mode for tests
npm run test:watch
```

### Infrastructure (CDK)

```bash
cd infrastructure

# Install dependencies
npm install

# Compile TypeScript
npm run build

# Watch mode
npm run watch

# Synthesize CloudFormation
npx cdk synth

# Deploy all stacks
npx cdk deploy --all

# Deploy specific stack
npx cdk deploy InfrastructureStack

# Show differences
npx cdk diff

# Destroy stacks
npx cdk destroy --all
```

### Docker

```bash
# Build App API image
docker build -f backend/Dockerfile.app-api -t app-api:latest .

# Build Inference API image
docker build -f backend/Dockerfile.inference-api -t inference-api:latest .

# Run with Docker Compose (if available)
docker-compose up
```

### Testing

```bash
# Backend tests
cd backend
source venv/bin/activate
python -m pytest tests/ -v
python -m pytest tests/ -v --cov=src  # With coverage

# Frontend tests
cd frontend/ai.client
npm test                    # Run once
npm run test:watch          # Watch mode
npm run test:coverage       # With coverage
```

## Environment Configuration

### Backend (.env)

Located at `backend/src/.env`:

```bash
AWS_REGION=us-east-1
AWS_PROFILE=default
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AGENTCORE_MEMORY_ID=<memory-id>
AGENTCORE_RUNTIME_ID=<runtime-id>
TAVILY_API_KEY=<optional>
NOVA_ACT_API_KEY=<optional>
```

### Frontend (environment.ts)

Located at `frontend/ai.client/src/environments/`:

```typescript
export const environment = {
  production: false,
  appApiUrl: 'http://localhost:8000',
  inferenceApiUrl: 'http://localhost:8001',
  enableAuthentication: true
};
```

## Package Management

### Backend

- **File**: `backend/pyproject.toml`
- **Strategy**: Single source of truth with optional dependencies
- **Groups**: `agentcore`, `dev`, `all`

### Frontend

- **File**: `frontend/ai.client/package.json`
- **Manager**: npm (locked to 11.2.0)

### Infrastructure

- **File**: `infrastructure/package.json`
- **Manager**: npm
- **CDK Version**: 2.1033.0+

## Build Outputs

- **Frontend**: `frontend/ai.client/dist/`
- **Backend**: No build step (Python interpreted)
- **Infrastructure**: `infrastructure/cdk.out/` (CloudFormation templates)

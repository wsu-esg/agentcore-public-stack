# AgentCore Public Stack - Developer Context

## Project Overview

**Name:** AgentCore Public Stack
**Purpose:** A production-ready multi-agent conversational AI system using AWS Bedrock AgentCore and Strands Agents.
**Key Features:**
*   **Multi-Agent Orchestration:** Uses Strands Agent.
*   **MCP Tool Integration:** Connects to Wikipedia, ArXiv, Google Search, etc., via Model Context Protocol (MCP) and AgentCore Gateway.
*   **Multimodal:** Supports text, images, and document inputs/outputs.
*   **Memory:** Two-tier memory system (session-based short-term and persistent long-term).
*   **Full-Stack:** Angular frontend, Python FastAPI backend, AWS CDK infrastructure.

## Architecture & Tech Stack

### Frontend (`frontend/ai.client`)
*   **Framework:** Angular v21
*   **Styling:** Tailwind CSS v4.1
*   **Language:** TypeScript
*   **State Management:** Signals, RxJS
*   **Key Dependencies:** `@microsoft/fetch-event-source` (SSE), `marked` (Markdown), `mermaid`, `katex`.

### Backend (`backend`)
*   **Framework:** FastAPI (Python 3.9+)
*   **AI Orchestration:** Strands Agents (`strands-agents`)
*   **AWS SDK:** Boto3
*   **API Pattern:**
    *   `app_api`: Main application logic, chat, auth.
    *   `inference_api`: Bedrock inference handling.
*   **Streaming:** Server-Sent Events (SSE).

### Infrastructure (`infrastructure`)
*   **IaC:** AWS CDK v2 (TypeScript)
*   **Compute:** AWS Fargate (ECS) for APIs, Lambda for Gateway tools.
*   **Storage:** DynamoDB (sessions, user data), S3 (assets).
*   **Networking:** VPC, ALB, CloudFront.

## Directory Structure

*   **`backend/`**: Python backend source code.
    *   `src/agents`: Main agent logic and tools.
    *   `src/apis`: API route definitions (`app_api`, `inference_api`).
*   **`frontend/`**: Angular frontend source code.
    *   `ai.client/src/app`: Application components and services.
*   **`infrastructure/`**: AWS CDK stacks.
    *   `lib/`: Stack definitions (`app-api-stack`, `frontend-stack`, `gateway-stack`, etc.).
*   **`scripts/`**: Utility scripts for build, deploy, and test.

## Development Workflow

### Prerequisites
*   Node.js 18+
*   Python 3.13+
*   Docker
*   AWS CLI configured

### Setup & Run
1.  **Setup Dependencies:**
    ```bash
    ./setup.sh
    ```
2.  **Configure Environment:**
    *   Copy `backend/src/.env.example` to `backend/src/.env`.
    *   Fill in AWS credentials and region.
3.  **Start Locally:**
    ```bash
    ./start.sh
    ```
    *   Frontend: `http://localhost:4200`
    *   Backend: `http://localhost:8000`

### Testing
*   **Backend:** `pytest` (run from `backend/src`)
*   **Frontend:** `ng test` (run from `frontend/ai.client`)

## Key Conventions

*   **Tooling:** Tools are defined in `backend/src/agents/main_agent/tools`. Local tools use the `@tool` decorator.
*   **Styling:** Use Tailwind utility classes.
*   **State:** Use Angular Signals for reactive state management.
*   **API Communication:** The frontend communicates with the backend via HTTP and SSE for chat streaming.

## Important Files
*   `README.md`: Comprehensive project documentation.
*   `CLAUDE.MD`: Specific instructions for AI agents (contains architecture diagrams and detailed flows).
*   `backend/pyproject.toml`: Python dependencies.
*   `frontend/ai.client/package.json`: Frontend dependencies.
*   `infrastructure/cdk.json`: CDK configuration.

# Dev Environment — MANDATORY Container Execution Rules

All runtime operations MUST execute inside the Docker container. The host machine is ONLY for reading and writing code files via Kiro.

## What MUST run inside the container (`docker compose exec dev <command>`)

- Syntax checking and compilation (`python3 -c`, `tsc`, `ng build`, `npm run build`)
- Running tests (`pytest`, `vitest`, `npm test`)
- Installing dependencies (`pip install`, `npm install`)
- Linting and formatting (`ruff`, `black`, `eslint`, `prettier`)
- Type checking (`mypy`, `tsc --noEmit`)
- AWS CLI commands (`aws`, `cdk synth`, `cdk deploy`, `cdk diff`)
- Running scripts (`python3 backend/scripts/...`, `bash scripts/...`)
- Package management (`pip`, `npm`, `npx`)
- Git operations (`git`, `gh`)
- Docker builds (`docker build`)
- Any command that imports project dependencies or executes project code

## What runs on the host (NO container)

- Reading and writing files (Kiro file tools)
- `docker compose up -d --build` (manages the container itself)
- `docker compose ps` (checks container status)
- `docker compose down` (stops the container)

## Command format

```bash
docker compose exec dev <command>
```

## Workspace path inside container

The repo is mounted at `/workspace/bsu-org/agentcore-public-stack/` inside the container. When running commands that need the project root, use that path or `cd` into it.

## NO EXCEPTIONS

Do NOT run `python3`, `pip`, `npm`, `node`, `pytest`, `ruff`, `black`, `mypy`, `aws`, `cdk`, or any build/test/lint/deploy command directly on the host. Always prefix with `docker compose exec dev`. If a command fails inside the container due to missing dependencies, install them inside the container first.

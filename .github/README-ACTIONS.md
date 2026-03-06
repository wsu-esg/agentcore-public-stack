# GitHub Actions — Deploy Guide

This guide walks you through deploying the AgentCore Public Stack from a fork of this repository. Follow the steps in order — each one builds on the last.

## Step A: Prepare Your AWS Account

Before touching GitHub, you need three things set up in AWS.

### A1. Set Up AWS Authentication

Choose one method. Your GitHub workflows will use these credentials to deploy resources.

**Option 1: OIDC Role (recommended)** — no long-lived keys to rotate.

Follow these guides to create an OIDC identity provider and an IAM role that GitHub Actions can assume:
- [GitHub Docs: Configuring OpenID Connect in Amazon Web Services](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS Docs: Create an OpenID Connect (OIDC) identity provider in IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)

Make note of the IAM role ARN — you'll need it in Step B.

**Option 2: IAM Access Keys (simpler, less secure)**

Create an IAM user with programmatic access and generate an access key pair. Make note of the Access Key ID and Secret Access Key — you'll need them in Step B.

### A2. Create a Route 53 Hosted Zone

Create a public hosted zone for your domain (e.g. `example.com`).

See: [Creating a public hosted zone](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/CreatingHostedZone.html)

### A3. Create ACM Certificates

You need two certificates. Each should cover both your apex domain and subdomains (e.g. `example.com` and `*.example.com`). When requesting the certificate in ACM, add `*.example.com` as an additional domain name so it covers subdomains like `api.example.com` and `app.example.com`.

| Certificate | Region | Used By |
|-------------|--------|---------|
| ALB certificate | Your deployment region (e.g. `us-west-2`) | Application Load Balancer (`api.example.com`) |
| CloudFront certificate | `us-east-1` (required by CloudFront) | Frontend CDN (`app.example.com`) |

See: [Requesting a public certificate](https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-request-public.html)

---

## Step B: Configure GitHub Repository

Go to your forked repository: **Settings → Secrets and variables → Actions**

### Secrets

These are encrypted values that never appear in logs.

| Name | Required | Description |
|------|:--------:|-------------|
| `AWS_ROLE_ARN` | If using OIDC | IAM role ARN from Step A1 |
| `AWS_ACCESS_KEY_ID` | If using keys | IAM access key from Step A1 |
| `AWS_SECRET_ACCESS_KEY` | If using keys | IAM secret key from Step A1 |

### Variables

These are non-sensitive configuration values.

| Name | Required | Example | Description |
|------|:--------:|---------|-------------|
| `AWS_REGION` | Yes | `us-west-2` | AWS region for all resources |
| `CDK_AWS_ACCOUNT` | Yes | `123456789012` | Your 12-digit AWS account ID |
| `CDK_PROJECT_PREFIX` | Yes | `agentcore` | Unique prefix for all AWS resource names |
| `CDK_HOSTED_ZONE_DOMAIN` | Yes | `example.com` | Route 53 hosted zone domain (from Step A2) |
| `CDK_ALB_SUBDOMAIN` | Yes | `api` | Subdomain for the ALB (e.g. `api.example.com`) |
| `CDK_DOMAIN_NAME` | Yes | `app.example.com` | Custom domain for the CloudFront distribution |
| `CDK_CERTIFICATE_ARN` | Yes | `arn:aws:acm:us-west-2:...` | ACM certificate ARN for the ALB (from Step A3, in your deployment region) |
| `CDK_FRONTEND_CERTIFICATE_ARN` | Yes | `arn:aws:acm:us-east-1:...` | ACM certificate ARN for CloudFront (from Step A3, must be `us-east-1`) |

### Identity Provider (for user login)

These values come from your OIDC-compatible identity provider (e.g. Microsoft Entra ID, AWS Cognito, Okta). Step 7 uses them to seed the auth provider configuration so users can log in.

| Name | Type | Required | Example | Description |
|------|------|:--------:|---------|-------------|
| `SEED_AUTH_PROVIDER_ID` | Variable | Yes | `entra-id` | Slug identifier for the provider |
| `SEED_AUTH_DISPLAY_NAME` | Variable | Yes | `Microsoft Entra ID` | Display name shown on the login page |
| `SEED_AUTH_ISSUER_URL` | Variable | Yes | `https://login.microsoftonline.com/TENANT/v2.0` | OIDC issuer URL from your IdP |
| `SEED_AUTH_CLIENT_ID` | Variable | Yes | `your-client-id` | OAuth client ID from your IdP |
| `SEED_AUTH_CLIENT_SECRET` | Secret | Yes | — | OAuth client secret from your IdP |
| `ENV_APP_API_ADMIN_JWT_ROLES` | Variable | No | `["Admin"]` | JSON array of JWT roles that grant system admin access. Must match a role claim from your IdP. |

That's it for required config. All other values have sensible defaults — see [ACTIONS-REFERENCE.md](./ACTIONS-REFERENCE.md) for the full list.

---

## Step C: Deploy

Go to the **Actions** tab and run each workflow in order. Wait for each step to complete before starting the next.

| Order | Workflow | Status |
|:-----:|---------|--------|
| 1 | [Deploy Infrastructure (VPC, ALB, ECS)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/infrastructure.yml) | [![Step 1](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/infrastructure.yml/badge.svg)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/infrastructure.yml) |
| 2 | [Deploy RAG Ingestion](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/rag-ingestion.yml) | [![Step 2](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/rag-ingestion.yml/badge.svg)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/rag-ingestion.yml) |
| 3 | [Deploy Inference API (AgentCore Runtime)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/inference-api.yml) | [![Step 3](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/inference-api.yml/badge.svg)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/inference-api.yml) |
| 4 | [Deploy App API (Backend)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/app-api.yml) | [![Step 4](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/app-api.yml/badge.svg)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/app-api.yml) |
| 5 | [Deploy Frontend (CloudFront)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/frontend.yml) | [![Step 5](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/frontend.yml/badge.svg)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/frontend.yml) |
| 6 | [Deploy Gateway (Lambda Tools)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/gateway.yml) | [![Step 6](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/gateway.yml/badge.svg)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/gateway.yml) |
| 7 | [Seed Bootstrap Data](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/bootstrap-data-seeding.yml) | [![Step 7](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/bootstrap-data-seeding.yml/badge.svg)](https://github.com/Boise-State-Development/agentcore-public-stack/actions/workflows/bootstrap-data-seeding.yml) |

All workflows default to the **production** environment when triggered manually.

---

## Optional Integrations

| Name | Type | Description |
|------|------|-------------|
| `ENV_INFERENCE_API_TAVILY_API_KEY` | Secret | Tavily API key for web search |
| `ENV_INFERENCE_API_NOVA_ACT_API_KEY` | Secret | Amazon Nova Act API key for browser automation |

---

## Full Configuration Reference

For every available configuration variable, see [ACTIONS-REFERENCE.md](./ACTIONS-REFERENCE.md).

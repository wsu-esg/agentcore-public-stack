#!/bin/bash
set -euo pipefail

# Deploy Frontend Stack (unified)
# Orchestrates the full frontend deployment:
#   1. Build Angular application
#   2. Deploy CDK infrastructure (S3 + CloudFront)
#   3. Sync assets to S3 and invalidate CloudFront cache
#
# Used by the nightly workflow as a single-command deploy.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# ============================================================
# Step 1: Build Frontend
# ============================================================
log_info "Step 1/3: Building frontend application..."
bash "${SCRIPT_DIR}/build.sh"

# ============================================================
# Step 2: Deploy CDK Infrastructure (S3 bucket + CloudFront)
# ============================================================
log_info "Step 2/3: Deploying CDK infrastructure..."
bash "${SCRIPT_DIR}/deploy-cdk.sh"

# ============================================================
# Step 3: Deploy Assets (S3 sync + CloudFront invalidation)
# ============================================================
log_info "Step 3/3: Deploying frontend assets..."
bash "${SCRIPT_DIR}/deploy-assets.sh"

log_info "Frontend deployment completed successfully!"

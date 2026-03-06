#!/bin/bash
set -euo pipefail

# Script: Bootstrap Data Seeding
# Description: Resolves resource names from SSM and invokes the Python seed script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Source common environment loader
source "${PROJECT_ROOT}/scripts/common/load-env.sh"

log_success() {
    echo -e "\033[0;32m✓ $1\033[0m"
}

main() {
    log_info "Starting bootstrap data seeding..."

    local prefix="${CDK_PROJECT_PREFIX}"
    local region="${CDK_AWS_REGION}"

    # Resolve DynamoDB table names and Secrets Manager ARN from SSM
    log_info "Resolving resource names from SSM Parameter Store..."

    export DDB_AUTH_PROVIDERS_TABLE
    DDB_AUTH_PROVIDERS_TABLE=$(aws ssm get-parameter \
        --name "/${prefix}/auth/auth-providers-table-name" \
        --region "${region}" \
        --query "Parameter.Value" \
        --output text)
    log_info "Auth providers table: ${DDB_AUTH_PROVIDERS_TABLE}"

    export SECRETS_AUTH_ARN
    SECRETS_AUTH_ARN=$(aws ssm get-parameter \
        --name "/${prefix}/auth/auth-provider-secrets-arn" \
        --region "${region}" \
        --query "Parameter.Value" \
        --output text)
    log_info "Auth secrets ARN: ${SECRETS_AUTH_ARN:0:50}..."

    export DDB_USER_QUOTAS_TABLE
    DDB_USER_QUOTAS_TABLE=$(aws ssm get-parameter \
        --name "/${prefix}/quota/user-quotas-table-name" \
        --region "${region}" \
        --query "Parameter.Value" \
        --output text)
    log_info "User quotas table: ${DDB_USER_QUOTAS_TABLE}"

    export DDB_MANAGED_MODELS_TABLE
    DDB_MANAGED_MODELS_TABLE=$(aws ssm get-parameter \
        --name "/${prefix}/admin/managed-models-table-name" \
        --region "${region}" \
        --query "Parameter.Value" \
        --output text)
    log_info "Managed models table: ${DDB_MANAGED_MODELS_TABLE}"

    export AWS_REGION="${region}"

    # Invoke the Python seed script
    log_info "Running seed script..."
    python3 "${PROJECT_ROOT}/backend/scripts/seed_bootstrap_data.py"

    log_success "Bootstrap data seeding complete!"
}

main "$@"

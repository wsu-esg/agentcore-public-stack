#!/bin/bash
set -euo pipefail

# Script: Teardown Nightly Stack
# Description: Empties S3 buckets and destroys all CDK stacks for nightly deployment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Empty S3 bucket
empty_bucket() {
    local bucket_name="$1"
    
    log_info "Emptying bucket: ${bucket_name}"
    
    # Check if bucket exists
    if ! aws s3api head-bucket --bucket "${bucket_name}" 2>/dev/null; then
        log_warn "Bucket ${bucket_name} does not exist, skipping"
        return 0
    fi
    
    # Delete all object versions and delete markers
    aws s3api list-object-versions \
        --bucket "${bucket_name}" \
        --output json \
        --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
        | jq -r '.Objects[]? | "--key \(.Key) --version-id \(.VersionId)"' \
        | xargs -r -n 2 aws s3api delete-object --bucket "${bucket_name}" || true
    
    aws s3api list-object-versions \
        --bucket "${bucket_name}" \
        --output json \
        --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
        | jq -r '.Objects[]? | "--key \(.Key) --version-id \(.VersionId)"' \
        | xargs -r -n 2 aws s3api delete-object --bucket "${bucket_name}" || true
    
    # Delete all objects (non-versioned)
    aws s3 rm "s3://${bucket_name}" --recursive || true
    
    log_success "Bucket ${bucket_name} emptied"
}

# Find and empty all S3 buckets with nightly prefix
empty_nightly_buckets() {
    log_info "Finding S3 buckets with prefix: ${CDK_PROJECT_PREFIX}"
    
    local buckets=$(aws s3api list-buckets \
        --query "Buckets[?starts_with(Name, '${CDK_PROJECT_PREFIX}')].Name" \
        --output text)
    
    if [ -z "${buckets}" ]; then
        log_info "No S3 buckets found with prefix ${CDK_PROJECT_PREFIX}"
        return 0
    fi
    
    log_info "Found buckets: ${buckets}"
    
    for bucket in ${buckets}; do
        empty_bucket "${bucket}"
    done
    
    log_success "All nightly S3 buckets emptied"
}

# Force delete Secrets Manager secrets (bypasses 7-day recovery window)
force_delete_secrets() {
    log_info "Force-deleting Secrets Manager secrets with prefix: ${CDK_PROJECT_PREFIX}"

    local secret_names=(
        "${CDK_PROJECT_PREFIX}-auth-secret"
        "${CDK_PROJECT_PREFIX}-oauth-client-secrets"
        "${CDK_PROJECT_PREFIX}-auth-provider-secrets"
    )

    for secret_name in "${secret_names[@]}"; do
        log_info "Force-deleting secret: ${secret_name}"
        aws secretsmanager delete-secret \
            --secret-id "${secret_name}" \
            --force-delete-without-recovery \
            --region "${CDK_AWS_REGION}" 2>/dev/null && \
            log_success "Secret ${secret_name} force-deleted" || \
            log_warn "Secret ${secret_name} not found or already deleted, skipping"
    done
}

# Destroy CDK stacks
destroy_stacks() {
    log_info "Destroying CDK stacks with prefix: ${CDK_PROJECT_PREFIX}"
    
    cd "${PROJECT_ROOT}/infrastructure"
    
    # Destroy all stacks (order doesn't matter with --force)
    npx cdk destroy --all --force || {
        log_error "CDK destroy failed, but continuing..."
        return 1
    }
    
    log_success "All CDK stacks destroyed"
}

main() {
    log_info "Starting teardown of nightly deployment..."
    
    # Validate required environment variables
    if [ -z "${CDK_PROJECT_PREFIX:-}" ]; then
        log_error "CDK_PROJECT_PREFIX environment variable is required"
        exit 1
    fi
    
    if [ -z "${CDK_AWS_REGION:-}" ]; then
        log_error "CDK_AWS_REGION environment variable is required"
        exit 1
    fi
    
    log_info "Project prefix: ${CDK_PROJECT_PREFIX}"
    log_info "AWS region: ${CDK_AWS_REGION}"
    
    # Empty S3 buckets first
    empty_nightly_buckets
    
    # Force-delete Secrets Manager secrets before CDK destroy
    # CloudFormation only schedules secrets for deletion (7-day recovery window),
    # which causes the next nightly deploy to fail with "already exists" errors.
    force_delete_secrets
    
    # Destroy CDK stacks
    destroy_stacks
    
    log_success "Nightly deployment teardown complete!"
}

main "$@"

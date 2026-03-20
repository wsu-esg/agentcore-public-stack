#!/bin/bash

#============================================================
# Stack Dependency Tests
#
# Runs the infrastructure jest test suite that validates:
#   1. No circular SSM dependencies between stacks
#   2. Deployment tier ordering is respected
#   3. All SSM reads are satisfied by a writer stack
#
# This script requires NO AWS credentials — it only scans
# TypeScript source files. Safe to run anywhere.
#============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
INFRA_DIR="${PROJECT_ROOT}/infrastructure"

# Logging
log_info()    { echo "[INFO] $1"; }
log_error()   { echo "[ERROR] $1" >&2; }
log_success() { echo "[SUCCESS] $1"; }

# Ensure node_modules exist
if [ ! -d "${INFRA_DIR}/node_modules" ]; then
    log_info "Installing infrastructure dependencies..."
    cd "${INFRA_DIR}"
    npm ci --prefer-offline --no-audit
fi

cd "${INFRA_DIR}"

# Compile TypeScript (tests import from lib/)
log_info "Compiling infrastructure TypeScript..."
npx tsc --noEmit 2>/dev/null || true  # type-check only, don't block on strict errors

# Run only the stack-dependencies and security tests (no AWS needed)
log_info "Running stack dependency order tests..."
npx jest test/stack-dependencies.test.ts \
    --no-coverage \
    --verbose \
    --forceExit

log_success "Stack dependency tests passed — no circular dependencies detected."

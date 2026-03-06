#!/bin/bash
set -euo pipefail

# Script: Install Dependencies for Bootstrap Data Seeding
# Description: Installs Python dependencies needed by seed_bootstrap_data.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Logging functions
log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_success() {
    echo "[SUCCESS] $1"
}

main() {
    log_info "Installing Bootstrap Data Seeding dependencies..."

    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed. Please install Python 3.13 or higher."
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version)
    log_info "Using ${PYTHON_VERSION}"

    # Upgrade pip
    log_info "Upgrading pip..."
    python3 -m pip install --upgrade pip

    # Install required dependencies
    log_info "Installing boto3 and httpx..."
    python3 -m pip install boto3 httpx

    # Verify installation
    log_info "Verifying installation..."
    if python3 -c "import boto3" 2>/dev/null; then
        log_success "boto3 installed successfully"
    else
        log_error "boto3 installation verification failed"
        exit 1
    fi

    if python3 -c "import httpx" 2>/dev/null; then
        log_success "httpx installed successfully"
    else
        log_error "httpx installation verification failed"
        exit 1
    fi

    log_success "Bootstrap Data Seeding dependencies installed successfully!"
}

main "$@"

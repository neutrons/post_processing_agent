#!/bin/bash
#
# Test runner for RPM systemd scriptlets
# Builds and tests the RPM in a Docker container
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Change to project root directory
cd "$(dirname "$0")/../.."

log_info "Building Docker test image for RPM scriptlets testing..."

# Build the test Docker image
if docker build -f tests/integration/Dockerfile.rpm-test -t postprocess-rpm-test .; then
    log_success "Docker test image built successfully"
else
    log_error "Failed to build Docker test image"
    exit 1
fi

log_info "Running RPM scriptlets tests in Docker container..."

# Run the tests in the container
if docker run --rm --privileged postprocess-rpm-test; then
    log_success "All RPM scriptlets tests passed!"
else
    log_error "RPM scriptlets tests failed"
    exit 1
fi

log_success "RPM scriptlets testing completed successfully!"

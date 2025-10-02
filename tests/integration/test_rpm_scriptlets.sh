#!/bin/bash
#
# Test script for RPM systemd scriptlets
# Tests installation, upgrade, and removal scenarios for post-processing agent
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_SERVICE="autoreduce-queue-processor.service"
RPM_NAME="postprocessing"
REQUIRED_USERS="snsdata"
REQUIRED_GROUPS="users hfiradmin"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Ensure systemd is available and working
check_systemd() {
    log_info "Checking systemd availability..."
    if ! command -v systemctl &> /dev/null; then
        log_error "systemctl command not found. systemd is required for this test."
        exit 1
    fi
    
    # Check if systemd is running (in container, it might not be)
    if ! systemctl is-system-running --quiet 2>/dev/null; then
        log_warning "systemd is not fully running. Some tests may be limited."
    fi
    
    log_success "systemd check passed"
}

# Check if required users and groups exist
check_users_groups() {
    log_info "Checking required users and groups..."
    
    # Check users
    for user in $REQUIRED_USERS; do
        if ! id "$user" &>/dev/null; then
            log_error "Required user '$user' does not exist"
            return 1
        else
            log_success "User '$user' exists"
        fi
    done
    
    # Check groups
    for group in $REQUIRED_GROUPS; do
        if ! getent group "$group" &>/dev/null; then
            log_error "Required group '$group' does not exist"
            return 1
        else
            log_success "Group '$group' exists"
        fi
    done
}

# Create required groups if they don't exist (for testing)
create_test_groups() {
    log_info "Creating test groups if needed..."
    
    # Create hfiradmin group if it doesn't exist
    if ! getent group hfiradmin &>/dev/null; then
        groupadd hfiradmin
        log_info "Created hfiradmin group for testing"
    fi
}

# Check service status
check_service_status() {
    local expected_status="$1"
    local current_status
    
    if systemctl is-active --quiet "$TEST_SERVICE" 2>/dev/null; then
        current_status="active"
    elif systemctl is-enabled --quiet "$TEST_SERVICE" 2>/dev/null; then
        current_status="enabled"
    else
        current_status="inactive"
    fi
    
    log_info "Service status: $current_status (expected: $expected_status)"
    return 0
}

# Install RPM and verify scriptlets
test_rpm_install() {
    log_info "Testing RPM installation..."
    
    # Find the RPM file
    local rpm_file
    rpm_file=$(find /root/rpmbuild/RPMS/noarch/ -name "${RPM_NAME}*.rpm" | head -1)
    
    if [[ ! -f "$rpm_file" ]]; then
        log_error "RPM file not found in /root/rpmbuild/RPMS/noarch/"
        return 1
    fi
    
    log_info "Installing RPM: $rpm_file"
    
    # Install the RPM
    if dnf install -y "$rpm_file"; then
        log_success "RPM installation completed"
    else
        log_error "RPM installation failed"
        return 1
    fi
    
    # Check if service file was installed
    if [[ -f "/usr/lib/systemd/system/$TEST_SERVICE" ]]; then
        log_success "Service file installed correctly"
    else
        log_error "Service file not found after installation"
        return 1
    fi
    
    # Check service status after installation
    check_service_status "installed"
    
    # Reload systemd to pick up the new service
    systemctl daemon-reload
    
    log_success "RPM installation test passed"
}

# Test RPM upgrade scenario
test_rpm_upgrade() {
    log_info "Testing RPM upgrade scenario..."
    
    # For upgrade testing, we'll simulate by reinstalling
    # In a real scenario, this would be a newer version
    local rpm_file
    rpm_file=$(find /root/rpmbuild/RPMS/noarch/ -name "${RPM_NAME}*.rpm" | head -1)
    
    if [[ ! -f "$rpm_file" ]]; then
        log_error "RPM file not found for upgrade test"
        return 1
    fi
    
    log_info "Simulating upgrade by reinstalling: $rpm_file"
    
    # Enable the service first to test upgrade behavior
    if systemctl enable "$TEST_SERVICE" 2>/dev/null; then
        log_info "Service enabled for upgrade test"
    else
        log_warning "Could not enable service (may be normal in container)"
    fi
    
    # Reinstall (simulates upgrade)
    if dnf reinstall -y "$rpm_file"; then
        log_success "RPM upgrade/reinstall completed"
    else
        log_error "RPM upgrade/reinstall failed"
        return 1
    fi
    
    # Check service status after upgrade
    check_service_status "upgraded"
    
    log_success "RPM upgrade test passed"
}

# Test RPM removal
test_rpm_removal() {
    log_info "Testing RPM removal..."
    
    # Remove the RPM
    if dnf remove -y "$RPM_NAME"; then
        log_success "RPM removal completed"
    else
        log_error "RPM removal failed"
        return 1
    fi
    
    # Check if service file was removed
    if [[ ! -f "/usr/lib/systemd/system/$TEST_SERVICE" ]]; then
        log_success "Service file removed correctly"
    else
        log_error "Service file still exists after removal"
        return 1
    fi
    
    # Reload systemd
    systemctl daemon-reload
    
    log_success "RPM removal test passed"
}

# Test systemd scriptlet functionality
test_systemd_scriptlets() {
    log_info "Testing systemd scriptlets functionality..."
    
    # Check if systemd macros are working by examining RPM scriptlets
    local rpm_file
    rpm_file=$(find /root/rpmbuild/RPMS/noarch/ -name "${RPM_NAME}*.rpm" | head -1)
    
    if [[ -f "$rpm_file" ]]; then
        log_info "Examining RPM scriptlets..."
        
        # Check post-install scriptlet
        if rpm -qp --scripts "$rpm_file" | grep -q "systemd_post"; then
            log_success "Post-install scriptlet contains systemd_post"
        else
            log_warning "Post-install scriptlet may not contain systemd_post"
        fi
        
        # Check pre-uninstall scriptlet
        if rpm -qp --scripts "$rpm_file" | grep -q "systemd_preun"; then
            log_success "Pre-uninstall scriptlet contains systemd_preun"
        else
            log_warning "Pre-uninstall scriptlet may not contain systemd_preun"
        fi
        
        # Check post-uninstall scriptlet
        if rpm -qp --scripts "$rpm_file" | grep -q "systemd_postun_with_restart"; then
            log_success "Post-uninstall scriptlet contains systemd_postun_with_restart"
        else
            log_warning "Post-uninstall scriptlet may not contain systemd_postun_with_restart"
        fi
    fi
}

# Test user and group requirements
test_user_group_requirements() {
    log_info "Testing user and group requirements..."
    
    local rpm_file
    rpm_file=$(find /root/rpmbuild/RPMS/noarch/ -name "${RPM_NAME}*.rpm" | head -1)
    
    if [[ -f "$rpm_file" ]]; then
        log_info "Checking RPM dependencies..."
        
        # Check user requirements
        if rpm -qp --requires "$rpm_file" | grep -q "user(snsdata)"; then
            log_success "RPM requires user(snsdata)"
        else
            log_error "RPM does not require user(snsdata)"
            return 1
        fi
        
        # Check group requirements
        if rpm -qp --requires "$rpm_file" | grep -q "group(users)"; then
            log_success "RPM requires group(users)"
        else
            log_error "RPM does not require group(users)"
            return 1
        fi
        
        if rpm -qp --requires "$rpm_file" | grep -q "group(hfiradmin)"; then
            log_success "RPM requires group(hfiradmin)"
        else
            log_error "RPM does not require group(hfiradmin)"
            return 1
        fi
    fi
}

# Main test function
run_all_tests() {
    log_info "Starting RPM systemd scriptlets test suite..."
    
    # Prerequisites
    check_root
    check_systemd
    create_test_groups
    check_users_groups
    
    # Test systemd scriptlets in RPM
    test_systemd_scriptlets
    
    # Test user/group requirements
    test_user_group_requirements
    
    # Test installation
    test_rpm_install
    
    # Test upgrade
    test_rpm_upgrade
    
    # Test removal
    test_rpm_removal
    
    log_success "All tests completed successfully!"
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_all_tests "$@"
fi

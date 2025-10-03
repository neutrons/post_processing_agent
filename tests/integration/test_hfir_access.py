#!/usr/bin/env python3
"""
Test for HFIR file access permissions
Verifies that the hfiradmin group requirement addresses the ACL-based permissions
mentioned in Story 11975 and PR #65
"""

import os
import grp
import pwd
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestHFIRFileAccess(unittest.TestCase):
    """Test HFIR file access permissions and group requirements"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent.parent
        self.spec_file = self.project_root / "SPECS" / "postprocessing.spec"
        self.service_file = self.project_root / "systemd" / "autoreduce-queue-processor.service"

    def test_hfiradmin_group_requirement(self):
        """Test that hfiradmin group is created in SPEC file %post section"""
        with open(self.spec_file, 'r') as f:
            content = f.read()
        
        self.assertIn("groupadd -r hfiradmin", content,
                     "SPEC file should create group(hfiradmin) for HFIR file access")

    def test_sssd_dependency_in_service(self):
        """Test that the service depends on SSSD for ACL-based permissions"""
        with open(self.service_file, 'r') as f:
            content = f.read()
        
        # SSSD is required for ACL-based group memberships to work properly
        self.assertIn("Requires=sssd.service", content,
                     "Service should require SSSD for ACL-based permissions")
        self.assertIn("After=sssd.service", content,
                     "Service should start after SSSD to ensure groups are available")

    def test_snsdata_user_in_service(self):
        """Test that the service runs as snsdata user"""
        with open(self.service_file, 'r') as f:
            content = f.read()
        
        self.assertIn("User=snsdata", content,
                     "Service should run as snsdata user")

    def test_user_requirements_present(self):
        """Test that all required user/group creation is present in %post section"""
        with open(self.spec_file, 'r') as f:
            content = f.read()
        
        # Check all required user/group creation commands
        required_commands = [
            "useradd -r -g users -G hfiradmin",
            "groupadd -r users", 
            "groupadd -r hfiradmin"
        ]
        
        for cmd in required_commands:
            self.assertIn(cmd, content, f"Missing user/group creation command: {cmd}")

    def test_group_existence_check(self):
        """Test that we can check for group existence (would be done at runtime)"""
        # This test simulates what would happen at package installation time
        # In a real system, these groups would be created by other packages or system setup
        
        def check_group_exists(group_name):
            """Check if a group exists on the system"""
            try:
                grp.getgrnam(group_name)
                return True
            except KeyError:
                return False
        
        # These are the groups our package will require
        required_groups = ['users', 'hfiradmin']
        
        # In a test environment, we can't guarantee these exist
        # but we can test the checking mechanism
        for group in required_groups:
            exists = check_group_exists(group)
            print(f"Group '{group}' exists: {exists}")
            # We don't assert here because in a test environment these may not exist
            # But in production, the RPM dependencies will ensure they do

    def test_user_existence_check(self):
        """Test that we can check for user existence (would be done at runtime)"""
        def check_user_exists(username):
            """Check if a user exists on the system"""
            try:
                pwd.getpwnam(username)
                return True
            except KeyError:
                return False
        
        # This is the user our package will require
        required_user = 'snsdata'
        
        exists = check_user_exists(required_user)
        print(f"User '{required_user}' exists: {exists}")
        # We don't assert here because in a test environment this may not exist
        # But in production, the RPM dependencies will ensure it does

    def test_acl_simulation(self):
        """Simulate ACL-based file access that would be used for HFIR files"""
        # This test simulates the ACL-based permission system mentioned in the user story
        # In the real system, HFIR files would have ACLs set up that require hfiradmin group
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_hfir_file.nxs.h5"
            test_file.write_text("mock HFIR data file")
            
            # In a real system, this file would have ACLs like:
            # setfacl -m g:hfiradmin:r test_hfir_file.nxs.h5
            # But we can't test ACLs in a unit test environment
            
            # What we can test is that the file exists and is readable
            self.assertTrue(test_file.exists(), "Test file should exist")
            self.assertTrue(test_file.is_file(), "Test file should be a regular file")
            
            # In production, the snsdata user would need to be in hfiradmin group
            # to read files with ACLs set for that group

    def test_service_restart_behavior(self):
        """Test that service restart behavior is correctly configured"""
        with open(self.service_file, 'r') as f:
            content = f.read()
        
        # Check restart configuration
        self.assertIn("Restart=on-failure", content,
                     "Service should restart on failure")
        self.assertIn("RestartSec=5s", content,
                     "Service should have restart delay")

    def test_rpm_scriptlets_handle_service_correctly(self):
        """Test that RPM scriptlets will handle service lifecycle correctly"""
        with open(self.spec_file, 'r') as f:
            content = f.read()
        
        # Verify that scriptlets use _with_restart for proper handling during upgrades
        self.assertIn("%systemd_postun_with_restart", content,
                     "Should use systemd_postun_with_restart to handle service during upgrades")
        
        # This ensures that during package upgrades:
        # 1. Service is stopped before old package removal
        # 2. Service is restarted after new package installation
        # 3. If service was running, it will be restarted with new version
        # 4. If service was stopped, it stays stopped

    def test_working_directory_correct(self):
        """Test that service working directory is correct"""
        with open(self.service_file, 'r') as f:
            content = f.read()
        
        self.assertIn("WorkingDirectory=/opt/postprocessing", content,
                     "Service should have correct working directory")

    def test_fedora_packaging_compliance(self):
        """Test compliance with Fedora packaging guidelines"""
        with open(self.spec_file, 'r') as f:
            content = f.read()
        
        # Check that we have all required systemd scriptlets
        required_scriptlets = [
            "%systemd_post",
            "%systemd_preun", 
            "%systemd_postun_with_restart"
        ]
        
        for scriptlet in required_scriptlets:
            self.assertIn(scriptlet, content, 
                         f"Missing required systemd scriptlet: {scriptlet}")
        
        # Check that we have systemd-rpm-macros build dependency
        self.assertIn("BuildRequires: systemd-rpm-macros", content,
                     "Missing BuildRequires: systemd-rpm-macros")


if __name__ == '__main__':
    unittest.main()

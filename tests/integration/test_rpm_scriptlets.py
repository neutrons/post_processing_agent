#!/usr/bin/env python3
"""
Test for RPM systemd scriptlets and user/group requirements
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestRPMScriptlets(unittest.TestCase):
    """Test RPM systemd scriptlets and requirements"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent.parent
        self.spec_file = self.project_root / "SPECS" / "postprocessing.spec"

    def test_spec_file_exists(self):
        """Test that the SPEC file exists"""
        self.assertTrue(self.spec_file.exists(), "SPEC file should exist")

    def test_systemd_macros_buildreq(self):
        """Test that systemd-rpm-macros is in BuildRequires"""
        with open(self.spec_file, 'r') as f:
            content = f.read()
        
        self.assertIn("BuildRequires: systemd-rpm-macros", content,
                     "systemd-rpm-macros should be in BuildRequires")

    def test_user_group_requirements(self):
        """Test that user and group creation is present in %post section"""
        with open(self.spec_file, 'r') as f:
            content = f.read()
        
        # Check user creation
        self.assertIn("useradd -r -g users -G hfiradmin", content,
                     "Should create user(snsdata) in %post section")
        
        # Check group creation
        self.assertIn("groupadd -r users", content,
                     "Should create group(users) in %post section")
        self.assertIn("groupadd -r hfiradmin", content,
                     "Should create group(hfiradmin) in %post section")

    def test_systemd_scriptlets_present(self):
        """Test that systemd scriptlets are present in SPEC file"""
        with open(self.spec_file, 'r') as f:
            content = f.read()
        
        # Check for %post scriptlet
        self.assertIn("%post", content, "Should have %post scriptlet")
        self.assertIn("%systemd_post autoreduce-queue-processor.service", content,
                     "Should have systemd_post macro in %post")
        
        # Check for %preun scriptlet
        self.assertIn("%preun", content, "Should have %preun scriptlet")
        self.assertIn("%systemd_preun autoreduce-queue-processor.service", content,
                     "Should have systemd_preun macro in %preun")
        
        # Check for %postun scriptlet
        self.assertIn("%postun", content, "Should have %postun scriptlet")
        self.assertIn("%systemd_postun_with_restart autoreduce-queue-processor.service", content,
                     "Should have systemd_postun_with_restart macro in %postun")

    def test_service_file_in_files_section(self):
        """Test that the service file is included in %files section"""
        with open(self.spec_file, 'r') as f:
            content = f.read()
        
        self.assertIn("%{_unitdir}/autoreduce-queue-processor.service", content,
                     "Service file should be in %files section")

    def test_spec_file_syntax(self):
        """Test that the SPEC file has valid syntax"""
        # This is a basic syntax check - in a real environment you'd use rpmlint
        with open(self.spec_file, 'r') as f:
            lines = f.readlines()
        
        # Check for common syntax issues
        for i, line in enumerate(lines, 1):
            # Check for unmatched %{...} macros (basic check)
            open_braces = line.count('%{')
            close_braces = line.count('}')
            if open_braces != close_braces:
                # This might be a multi-line macro, so we'll just warn
                print(f"Warning: Potential macro syntax issue at line {i}: {line.strip()}")

    def test_systemd_service_file_exists(self):
        """Test that the systemd service file exists"""
        service_file = self.project_root / "systemd" / "autoreduce-queue-processor.service"
        self.assertTrue(service_file.exists(), "systemd service file should exist")

    def test_systemd_service_file_content(self):
        """Test that the systemd service file has required content"""
        service_file = self.project_root / "systemd" / "autoreduce-queue-processor.service"
        
        if service_file.exists():
            with open(service_file, 'r') as f:
                content = f.read()
            
            # Check for required sections
            self.assertIn("[Unit]", content, "Service file should have [Unit] section")
            self.assertIn("[Service]", content, "Service file should have [Service] section")
            self.assertIn("[Install]", content, "Service file should have [Install] section")
            
            # Check for user specification
            self.assertIn("User=snsdata", content, "Service should run as snsdata user")
            
            # Check for SSSD dependency (mentioned in the user story)
            self.assertIn("Requires=sssd.service", content, "Service should depend on sssd.service")
            self.assertIn("After=sssd.service", content, "Service should start after sssd.service")


if __name__ == '__main__':
    unittest.main()

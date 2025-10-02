#!/usr/bin/env python3
"""
Final validation script for RPM systemd scriptlets implementation
Validates compliance with Fedora packaging guidelines
"""

import re
import sys
from pathlib import Path


class FedoraPackagingValidator:
    """Validator for Fedora packaging guidelines compliance"""
    
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.spec_file = self.project_root / "SPECS" / "postprocessing.spec"
        self.service_file = self.project_root / "systemd" / "autoreduce-queue-processor.service"
        self.errors = []
        self.warnings = []
        self.success = []
    
    def log_error(self, message):
        """Log a validation error"""
        self.errors.append(f"❌ ERROR: {message}")
    
    def log_warning(self, message):
        """Log a validation warning"""
        self.warnings.append(f"⚠️  WARNING: {message}")
    
    def log_success(self, message):
        """Log a validation success"""
        self.success.append(f"✅ SUCCESS: {message}")
    
    def validate_build_requirements(self):
        """Validate systemd build requirements"""
        if not self.spec_file.exists():
            self.log_error("SPEC file not found")
            return
        
        content = self.spec_file.read_text()
        
        if "BuildRequires: systemd-rpm-macros" in content:
            self.log_success("systemd-rpm-macros BuildRequires present")
        else:
            self.log_error("Missing BuildRequires: systemd-rpm-macros")
    
    def validate_systemd_scriptlets(self):
        """Validate systemd scriptlets presence and correctness"""
        if not self.spec_file.exists():
            return
        
        content = self.spec_file.read_text()
        
        # Check for %post scriptlet
        if "%post" in content and "%systemd_post autoreduce-queue-processor.service" in content:
            self.log_success("%post scriptlet with systemd_post macro present")
        else:
            self.log_error("Missing or incorrect %post scriptlet")
        
        # Check for %preun scriptlet
        if "%preun" in content and "%systemd_preun autoreduce-queue-processor.service" in content:
            self.log_success("%preun scriptlet with systemd_preun macro present")
        else:
            self.log_error("Missing or incorrect %preun scriptlet")
        
        # Check for %postun scriptlet
        if "%postun" in content and "%systemd_postun_with_restart autoreduce-queue-processor.service" in content:
            self.log_success("%postun scriptlet with systemd_postun_with_restart macro present")
        else:
            self.log_error("Missing or incorrect %postun scriptlet")
    
    def validate_user_group_requirements(self):
        """Validate user and group requirements"""
        if not self.spec_file.exists():
            return
        
        content = self.spec_file.read_text()
        
        required_deps = [
            ("user(snsdata)", "Service user requirement"),
            ("group(users)", "Users group requirement"),
            ("group(hfiradmin)", "HFIR admin group requirement")
        ]
        
        for dep, description in required_deps:
            if f"Requires: {dep}" in content:
                self.log_success(f"{description} present: {dep}")
            else:
                self.log_error(f"Missing requirement: {dep}")
    
    def validate_service_file(self):
        """Validate systemd service file"""
        if not self.service_file.exists():
            self.log_error("systemd service file not found")
            return
        
        content = self.service_file.read_text()
        
        # Check required sections
        required_sections = ["[Unit]", "[Service]", "[Install]"]
        for section in required_sections:
            if section in content:
                self.log_success(f"Service file has {section} section")
            else:
                self.log_error(f"Service file missing {section} section")
        
        # Check SSSD dependency
        if "Requires=sssd.service" in content:
            self.log_success("Service requires SSSD (needed for ACL groups)")
        else:
            self.log_error("Service should require SSSD for ACL-based groups")
        
        if "After=sssd.service" in content:
            self.log_success("Service starts after SSSD")
        else:
            self.log_error("Service should start after SSSD")
        
        # Check user specification
        if "User=snsdata" in content:
            self.log_success("Service runs as snsdata user")
        else:
            self.log_error("Service should specify User=snsdata")
        
        # Check restart behavior
        if "Restart=on-failure" in content:
            self.log_success("Service has restart on failure configured")
        else:
            self.log_warning("Consider adding Restart=on-failure")
    
    def validate_files_section(self):
        """Validate %files section includes service file"""
        if not self.spec_file.exists():
            return
        
        content = self.spec_file.read_text()
        
        if "%{_unitdir}/autoreduce-queue-processor.service" in content:
            self.log_success("Service file included in %files section")
        else:
            self.log_error("Service file not included in %files section")
    
    def validate_spec_syntax(self):
        """Basic SPEC file syntax validation"""
        if not self.spec_file.exists():
            return
        
        content = self.spec_file.read_text()
        lines = content.split('\n')
        
        # Check for common syntax issues
        for i, line in enumerate(lines, 1):
            # Check for unmatched %{...} macros
            open_braces = line.count('%{')
            close_braces = line.count('}')
            if open_braces != close_braces and open_braces > 0:
                self.log_warning(f"Potential macro syntax issue at line {i}: {line.strip()}")
        
        # Check for required fields
        required_fields = ["Name:", "Version:", "Release:", "Summary:", "License:", "URL:"]
        for field in required_fields:
            if field in content:
                self.log_success(f"SPEC file has {field}")
            else:
                self.log_error(f"SPEC file missing {field}")
    
    def validate_fedora_compliance(self):
        """Validate overall Fedora packaging guideline compliance"""
        # Check that we're following the systemd guidelines
        guidelines_checks = [
            ("Uses systemd-rpm-macros", lambda: "systemd-rpm-macros" in self.spec_file.read_text()),
            ("Uses correct scriptlet macros", lambda: all(macro in self.spec_file.read_text() for macro in ["%systemd_post", "%systemd_preun", "%systemd_postun_with_restart"])),
            ("Declares user/group dependencies", lambda: all(req in self.spec_file.read_text() for req in ["user(snsdata)", "group(users)", "group(hfiradmin)"]))
        ]
        
        for check_name, check_func in guidelines_checks:
            try:
                if check_func():
                    self.log_success(f"Fedora guideline compliance: {check_name}")
                else:
                    self.log_error(f"Fedora guideline violation: {check_name}")
            except Exception as e:
                self.log_error(f"Could not validate {check_name}: {e}")
    
    def run_all_validations(self):
        """Run all validation checks"""
        print("🔍 Running Fedora packaging guidelines validation...")
        print()
        
        self.validate_build_requirements()
        self.validate_systemd_scriptlets()
        self.validate_user_group_requirements()
        self.validate_service_file()
        self.validate_files_section()
        self.validate_spec_syntax()
        self.validate_fedora_compliance()
        
        # Print results
        print("\n📊 Validation Results:")
        print("=" * 50)
        
        if self.success:
            print("\n✅ Successful validations:")
            for message in self.success:
                print(f"  {message}")
        
        if self.warnings:
            print("\n⚠️  Warnings:")
            for message in self.warnings:
                print(f"  {message}")
        
        if self.errors:
            print("\n❌ Errors:")
            for message in self.errors:
                print(f"  {message}")
        
        print(f"\nSummary: {len(self.success)} passed, {len(self.warnings)} warnings, {len(self.errors)} errors")
        
        return len(self.errors) == 0


def main():
    """Main validation function"""
    # Determine project root (script is in tests/integration/)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent.parent
    
    validator = FedoraPackagingValidator(project_root)
    success = validator.run_all_validations()
    
    if success:
        print("\n🎉 All validations passed! RPM implementation is compliant with Fedora packaging guidelines.")
        return 0
    else:
        print(f"\n❌ Validation failed with {len(validator.errors)} errors. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

%global srcname postprocessing
%global summary postprocessing
%define release 1

Name: %{srcname}
Version: 4.1.0
Release: %{release}%{?dist}
Summary: %{summary}

License: MIT
URL: https://github.com/neutrons/post_processing_agent
Source: %{srcname}-%{version}.tar.gz
Group: Applications/Engineering

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildArch: noarch

BuildRequires:  python%{python3_pkgversion}-pip
BuildRequires: systemd-rpm-macros

Requires: python%{python3_pkgversion}
Requires: python%{python3_pkgversion}-psutil
Requires: python%{python3_pkgversion}-requests
Requires: python%{python3_pkgversion}-stomppy
Requires: python%{python3_pkgversion}-pyoncat
Requires: python-unversioned-command
Requires: systemd

prefix: /opt/postprocessing

%define site_packages %(python3 -c "import site; print(site.getsitepackages()[-1])")

%description
Post-processing agent to automatically catalog and reduce neutron data

%prep
%autosetup -p1 -n %{srcname}-%{version}

%build
# no build step

%install
%{python3} -m pip install --target %{buildroot}%{prefix} --no-deps .
%{__install} -m 755 %{buildroot}%{prefix}/postprocessing/queueProcessor.py %{buildroot}%{prefix}
%{__mkdir} -p %{buildroot}%{prefix}/log
%{__mkdir} -p %{buildroot}%{site_packages}
echo %{prefix} > %{buildroot}%{site_packages}/postprocessing.pth
%{__mkdir} -p -m 1755 %{buildroot}/var/log/SNS_applications/
%{__mkdir} -p %{buildroot}%{_unitdir}/
%{__install} -m 644 %{_sourcedir}/autoreduce-queue-processor.service %{buildroot}%{_unitdir}/

%files
%doc README.md
%license LICENSE.rst
%{prefix}/*
%attr(0755, -, -) %{prefix}/scripts
%{site_packages}/postprocessing.pth
%dir %attr(1755, -, -) /var/log/SNS_applications
%{_unitdir}/autoreduce-queue-processor.service

%post
# Create required groups if they don't exist
getent group users >/dev/null || groupadd -r users
getent group hfiradmin >/dev/null || groupadd -r hfiradmin
# Create required user if it doesn't exist
getent passwd snsdata >/dev/null || useradd -r -g users -G hfiradmin -d /var/lib/snsdata -s /sbin/nologin -c "SNS Data Processing User" snsdata
# Set ownership of log directory
chown snsdata:users /var/log/SNS_applications
chmod 1755 /var/log/SNS_applications
# Enable systemd service
%systemd_post autoreduce-queue-processor.service

%preun
%systemd_preun autoreduce-queue-processor.service

%postun
%systemd_postun_with_restart autoreduce-queue-processor.service

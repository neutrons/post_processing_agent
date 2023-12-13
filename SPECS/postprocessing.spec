%global srcname postprocessing
%global summary postprocessing
%define release 1

Name: %{srcname}
Version: 2.8.0
Release: %{release}%{?dist}
Summary: %{summary}

License: MIT
URL: https://github.com/neutrons/post_processing_agent
Source: %{srcname}-%{version}.tar.gz
Group: Applications/Engineering

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildArch: noarch
BuildRequires:  python%{python3_pkgversion}-pip
Requires: python%{python3_pkgversion}
Requires: python%{python3_pkgversion}-requests
Requires: python%{python3_pkgversion}-stomppy
Requires: python-unversioned-command

prefix: /opt/postprocessing

%define site_packages %(python3 -c "import site; print(site.getsitepackages()[-1])")

%description
Post-processing agent to automatically catalog and reduce neutron data

%prep
%autosetup -p1 -n %{srcname}-%{version}

%build

%install
%{python3} -m pip install --target %{buildroot}%{prefix} --no-deps .
mv %{buildroot}%{prefix}/postprocessing/queueProcessor.py %{buildroot}%{prefix}
mkdir -p %{buildroot}%{prefix}/log
mkdir -p %{buildroot}%{site_packages}
echo %{prefix} > %{buildroot}%{site_packages}/postprocessing.pth
mkdir -p %{buildroot}/var/log/SNS_applications

%files
%doc README.md
%license LICENSE.rst
%{prefix}/*
%attr(755, -, -) %{prefix}/scripts
%attr(755, -, -) %{prefix}/queueProcessor.py
%{site_packages}/postprocessing.pth
/var/log/SNS_applications

Summary: snsrepo
Name: snsrepo
Version: 1.0
Release: 1
Group: Applications/Engineering
BuildRoot: %{_tmppath}/%{name}
BuildArch: noarch
License: MIT
%define debug_package %{nil}

%description
Adds SNS repository

%prep

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/etc/yum.repos.d/
cat << EOF > %{buildroot}/etc/yum.repos.d/sns.repo
[sns]
name=RHEL $releasever SNS repo
baseurl=http://packages.sns.gov/distros/rhel/7/sns/RPMS
enabled=1
gpgcheck=0

[sns-source]
name=RHEL $releasever SNS Source repo
baseurl=http://packages.sns.gov/distros/rhel/7/sns/SRPMS
enabled=0
gpgcheck=0
EOF

%files
%attr(755, -, -) /etc/yum.repos.d/sns.repo

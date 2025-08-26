#!/bin/bash
# Script to set up development environment for CI
# This ensures the latest plot_publisher fixes are used

set -e

echo "Setting up development environment..."

# Install plot_publisher from GitHub with the latest fixes (PR #17)
pip install git+https://github.com/neutrons/plot_publisher.git

echo "Development environment setup complete!"

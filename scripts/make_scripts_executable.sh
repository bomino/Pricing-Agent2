#!/bin/bash

# Make all scripts executable
# Run this after cloning the repository

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Making all scripts executable..."

# Make all .sh files executable
find "$SCRIPT_DIR" -name "*.sh" -type f -exec chmod +x {} \;

# Make Python scripts executable
find "$SCRIPT_DIR" -name "*.py" -type f -exec chmod +x {} \;

echo "All scripts are now executable!"

# List executable scripts
echo ""
echo "Available scripts:"
find "$SCRIPT_DIR" -name "*.sh" -o -name "*.py" | sort
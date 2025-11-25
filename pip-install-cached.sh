#!/bin/bash
set -e

# Script to install Python packages from requirements.txt using a local cache
# Usage: ./pip-install-cached.sh <venv_path> <requirements_file> [cache_dir]

usage() {
    echo "Usage: $0 <venv_path> <requirements_file> [cache_dir]"
    echo ""
    echo "Arguments:"
    echo "  venv_path          Path to virtual environment (e.g., /opt/venv)"
    echo "  requirements_file  Path to requirements.txt (e.g., /workspace/requirements.txt)"
    echo "  cache_dir          Path to pip cache directory (optional, default: /workspace/pip-cache)"
    echo ""
    echo "Example:"
    echo "  $0 /opt/venv /workspace/requirements.txt"
    echo "  $0 /opt/venv /workspace/requirements.txt /workspace/custom-cache"
    exit 1
}

# Check arguments
if [ $# -lt 2 ]; then
    usage
fi

VENV_PATH="$1"
REQUIREMENTS_FILE="$2"
CACHE_DIR="${3:-/workspace/pip-cache}"

# Validate inputs
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Error: Requirements file not found at $REQUIREMENTS_FILE"
    exit 1
fi

echo "=== Cached Pip Installation ==="
echo "Virtual environment: $VENV_PATH"
echo "Requirements file: $REQUIREMENTS_FILE"
echo "Cache directory: $CACHE_DIR"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Verify activation
if [ "$VIRTUAL_ENV" != "$VENV_PATH" ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

echo "Active Python: $(which python)"
echo "Python version: $(python --version)"
echo ""

# Create cache directory if it doesn't exist
if [ ! -d "$CACHE_DIR" ]; then
    echo "Creating cache directory at $CACHE_DIR..."
    mkdir -p "$CACHE_DIR"
fi

# Check if cache is empty or missing packages
echo "Checking cache..."
CACHE_FILES=$(ls -1 "$CACHE_DIR"/*.whl "$CACHE_DIR"/*.tar.gz 2>/dev/null | wc -l || echo "0")

if [ "$CACHE_FILES" -eq 0 ]; then
    echo "Cache is empty. Downloading packages..."
    echo ""
    pip download -d "$CACHE_DIR" -r "$REQUIREMENTS_FILE"
    echo ""
    echo "✓ Packages downloaded to cache"
else
    echo "Found $CACHE_FILES cached package(s)"
    echo ""
    
    # Check if we need to download any new packages
    # Try installing with cache first, if it fails, update cache
    echo "Attempting installation from cache..."
    if ! pip install --no-index --find-links="$CACHE_DIR" -r "$REQUIREMENTS_FILE" 2>/dev/null; then
        echo ""
        echo "⚠ Some packages missing from cache. Downloading..."
        pip download -d "$CACHE_DIR" -r "$REQUIREMENTS_FILE"
        echo ""
        echo "✓ Cache updated"
    else
        echo "✓ All packages installed from cache (no network needed)"
        exit 0
    fi
fi

# Install packages from cache
echo ""
echo "Installing packages from cache..."
pip install --find-links="$CACHE_DIR" --no-index -r "$REQUIREMENTS_FILE"

echo ""
echo "=== Installation Complete ==="
echo "Installed packages:"
pip list | head -20
echo "..."
echo ""
echo "Cache location: $CACHE_DIR"
echo "Cache size: $(du -sh "$CACHE_DIR" | cut -f1)"
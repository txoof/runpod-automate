#!/bin/bash
set -e

echo "=== RunPod Setup Script ==="
echo ""

# Check if apt cache is older than 15 days
APT_LISTS="/var/lib/apt/lists"
CACHE_AGE_DAYS=15

if [ -d "$APT_LISTS" ]; then
    NEWEST_FILE=$(find "$APT_LISTS" -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
    if [ -n "$NEWEST_FILE" ]; then
        NOW=$(date +%s)
        AGE_DAYS=$(( (NOW - ${NEWEST_FILE%.*}) / 86400 ))
        
        if [ $AGE_DAYS -gt $CACHE_AGE_DAYS ]; then
            echo "Apt cache is $AGE_DAYS days old, updating..."
            apt-get update
        else
            echo "Apt cache is $AGE_DAYS days old, skipping update"
        fi
    else
        echo "Updating apt cache..."
        apt-get update
    fi
else
    echo "Updating apt cache..."
    apt-get update
fi

# Install common tools
echo ""
echo "Installing common tools..."
apt-get install -y vim curl wget git htop tmux

# Create global Python 3.11 venv
VENV_PATH="/opt/venv"

if [ ! -d "$VENV_PATH" ]; then
    echo ""
    echo "Creating global Python 3.11 virtual environment at $VENV_PATH..."
    python3.11 -m venv "$VENV_PATH"
    echo "Virtual environment created"
else
    echo ""
    echo "Virtual environment already exists at $VENV_PATH"
fi

# Add venv activation to bashrc if not already there
BASHRC="/root/.bashrc"
ACTIVATE_LINE="source $VENV_PATH/bin/activate"

if ! grep -q "$ACTIVATE_LINE" "$BASHRC" 2>/dev/null; then
    echo ""
    echo "Adding venv activation to .bashrc..."
    echo "" >> "$BASHRC"
    echo "# Auto-activate Python virtual environment" >> "$BASHRC"
    echo "$ACTIVATE_LINE" >> "$BASHRC"
    echo "Added to .bashrc"
else
    echo ""
    echo "Venv activation already in .bashrc"
fi

# Activate venv for current session
source "$VENV_PATH/bin/activate"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

echo ""
echo "=== Setup Complete ==="
echo "Virtual environment: $VENV_PATH"
echo "Activate with: source $VENV_PATH/bin/activate"#!/bin/bash
set -e

echo "=== RunPod Setup Script ==="
echo ""

# Check if apt cache is older than 15 days
APT_LISTS="/var/lib/apt/lists"
CACHE_AGE_DAYS=15

if [ -d "$APT_LISTS" ]; then
    NEWEST_FILE=$(find "$APT_LISTS" -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
    if [ -n "$NEWEST_FILE" ]; then
        NOW=$(date +%s)
        AGE_DAYS=$(( (NOW - ${NEWEST_FILE%.*}) / 86400 ))
        
        if [ $AGE_DAYS -gt $CACHE_AGE_DAYS ]; then
            echo "Apt cache is $AGE_DAYS days old, updating..."
            apt-get update
        else
            echo "Apt cache is $AGE_DAYS days old, skipping update"
        fi
    else
        echo "Updating apt cache..."
        apt-get update
    fi
else
    echo "Updating apt cache..."
    apt-get update
fi

# Install common tools
echo ""
echo "Installing common tools..."
apt-get install -y vim curl wget git htop tmux

# Check for custom packages
PACKAGES_FILE="/workspace/packages.txt"
if [ -f "$PACKAGES_FILE" ]; then
    echo ""
    echo "Found $PACKAGES_FILE, installing custom packages..."
    
    # Read packages from file, skipping comments and empty lines
    PACKAGES=$(grep -v '^#' "$PACKAGES_FILE" | grep -v '^[[:space:]]*$' | tr '\n' ' ')
    
    if [ -n "$PACKAGES" ]; then
        echo "Installing: $PACKAGES"
        apt-get install -y $PACKAGES
    else
        echo "No packages specified in $PACKAGES_FILE"
    fi
else
    echo ""
    echo "No $PACKAGES_FILE found, skipping custom packages"
fi

# Create global Python 3.11 venv
VENV_PATH="/opt/venv"

if [ ! -d "$VENV_PATH" ]; then
    echo ""
    echo "Creating global Python 3.11 virtual environment at $VENV_PATH..."
    python3.11 -m venv "$VENV_PATH"
    echo "Virtual environment created"
else
    echo ""
    echo "Virtual environment already exists at $VENV_PATH"
fi

# Add venv activation to bashrc if not already there
BASHRC="/root/.bashrc"
ACTIVATE_LINE="source $VENV_PATH/bin/activate"

if ! grep -q "$ACTIVATE_LINE" "$BASHRC" 2>/dev/null; then
    echo ""
    echo "Adding venv activation to .bashrc..."
    echo "" >> "$BASHRC"
    echo "# Auto-activate Python virtual environment" >> "$BASHRC"
    echo "$ACTIVATE_LINE" >> "$BASHRC"
    echo "Added to .bashrc"
else
    echo ""
    echo "Venv activation already in .bashrc"
fi

# Activate venv for current session
source "$VENV_PATH/bin/activate"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

echo ""
echo "=== Setup Complete ==="
echo "Virtual environment: $VENV_PATH"
echo "Activate with: source $VENV_PATH/bin/activate"
echo ""
echo "Add any additional apt packages to /workspace/packages.txt"

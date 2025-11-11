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

# Setup SSH keys for Git
SSH_DIR="/workspace/ssh"
SSH_KEY="$SSH_DIR/id_ed25519"
ROOT_SSH="/root/.ssh"
NEW_KEY_CREATED=false

echo ""
echo "=== Git SSH Key Setup ==="

# Create workspace SSH directory if it doesn't exist
if [ ! -d "$SSH_DIR" ]; then
    echo "Creating SSH directory at $SSH_DIR..."
    mkdir -p "$SSH_DIR"
    chmod 700 "$SSH_DIR"
fi

# Generate key if it doesn't exist
if [ ! -f "$SSH_KEY" ]; then
    echo "Generating new SSH key pair..."
    ssh-keygen -t ed25519 -f "$SSH_KEY" -N "" -C "runpod-workspace"
    chmod 600 "$SSH_KEY"
    chmod 644 "$SSH_KEY.pub"
    echo "SSH key generated successfully"
    NEW_KEY_CREATED=true
else
    echo "SSH key already exists at $SSH_KEY"
fi

# Setup ~/.ssh directory
mkdir -p "$ROOT_SSH"
chmod 700 "$ROOT_SSH"

# Symlink keys from workspace to ~/.ssh
if [ ! -L "$ROOT_SSH/id_ed25519" ]; then
    echo "Linking SSH keys to ~/.ssh..."
    ln -sf "$SSH_KEY" "$ROOT_SSH/id_ed25519"
    ln -sf "$SSH_KEY.pub" "$ROOT_SSH/id_ed25519.pub"
fi

# Create SSH config
cat > "$ROOT_SSH/config" <<EOF
Host github.com
    HostName github.com
    IdentityFile $ROOT_SSH/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

Host gitlab.com
    HostName gitlab.com
    IdentityFile $ROOT_SSH/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

Host bitbucket.org
    HostName bitbucket.org
    IdentityFile $ROOT_SSH/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
EOF

chmod 600 "$ROOT_SSH/config"

# Test if key is already registered with Git services
test_git_access() {
    local service=$1
    local host=$2
    
    # Try to SSH to git service (will fail but shows if key is accepted)
    if ssh -T -o ConnectTimeout=5 git@$host 2>&1 | grep -q "successfully authenticated\|You've successfully authenticated"; then
        return 0
    fi
    return 1
}

KEY_REGISTERED=false

echo ""
echo "Testing SSH key with Git services..."

if test_git_access "GitHub" "github.com"; then
    echo "  GitHub: Key is registered"
    KEY_REGISTERED=true
elif test_git_access "GitLab" "gitlab.com"; then
    echo "  GitLab: Key is registered"
    KEY_REGISTERED=true
elif test_git_access "Bitbucket" "bitbucket.org"; then
    echo "  Bitbucket: Key is registered"
    KEY_REGISTERED=true
fi

# Only prompt if a new key was created OR existing key is not registered
if [ "$NEW_KEY_CREATED" = true ] || [ "$KEY_REGISTERED" = false ]; then
    echo ""
    echo "=========================================="
    echo "PUBLIC KEY (add this to your Git hosting service):"
    echo "=========================================="
    cat "$SSH_KEY.pub"
    echo "=========================================="
    echo ""
    echo "To add this key to your Git repository:"
    echo ""
    echo "GitHub:"
    echo "  1. Copy the key above"
    echo "  2. Go to https://github.com/settings/keys"
    echo "  3. Click 'New SSH key'"
    echo "  4. Paste the key and save"
    echo ""
    echo "GitLab:"
    echo "  1. Copy the key above"
    echo "  2. Go to https://gitlab.com/-/profile/keys"
    echo "  3. Paste the key and save"
    echo ""
    echo "Bitbucket:"
    echo "  1. Copy the key above"
    echo "  2. Go to https://bitbucket.org/account/settings/ssh-keys/"
    echo "  3. Click 'Add key', paste and save"
    echo ""
    echo "Press Enter to continue after adding the key..."
    read
else
    echo "SSH key is already registered with a Git service"
fi

echo "SSH keys available at:"
echo "  Persistent: $SSH_KEY"
echo "  Symlinked: $ROOT_SSH/id_ed25519"

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
echo "SSH key location: $SSH_KEY"
echo "Activate venv with: source $VENV_PATH/bin/activate"
echo ""
echo "You can now clone your repositories with:"
echo "  git clone git@github.com:username/repo.git"
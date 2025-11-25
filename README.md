# RunPod CLI Tool - User Guide

A command-line tool for managing RunPod GPU instances with automatic SSH configuration, persistent storage, and setup automation.

## Prerequisites

- Python 3.7+
- RunPod account with API key
- `jq` for JSON parsing
- SSH client

### Install Dependencies

```bash
# Install Python package
pip install runpod requests

# Install jq
# On Ubuntu/Debian
sudo apt install jq

# On macOS
brew install jq
```

## Quick Start

### 1. Initial Setup

Run the setup command to configure your RunPod settings:

```bash
./runpod-cli.py setup
```

You'll be prompted for:
- **RunPod API Key** - Get from https://www.runpod.io/console/user/settings
- **GPU Type** - Search for a GPU (e.g., "3090", "4090")
- **Network Volume ID** - Create one first or leave blank
- **Docker Image** - Choose from PyTorch options or enter custom
- **Setup Script Path** - Path to your local setup.sh (optional)

### 2. Create a Network Volume (Optional but Recommended)

If you want persistent storage across pod restarts:

```bash
./create-volume.sh
```

This creates a network volume and updates your configuration with the volume ID.

### 3. Start a Pod

```bash
./runpod-cli.py up
```

This will:
- Create a pod with your configured GPU and image
- Wait for the pod to start (shows progress bar)
- Automatically configure SSH access
- Run your setup script if configured

### 4. Connect via SSH

After the pod starts:

```bash
ssh runpod
```

SSH configuration is automatically updated, so you can always use `ssh runpod` to connect.

## Commands

### setup
Configure RunPod settings (API key, GPU, image, volume, setup script)

```bash
./runpod-cli.py setup
```

### up
Start a GPU pod with configured settings

```bash
./runpod-cli.py up

# Override GPU type
./runpod-cli.py up --gpu "NVIDIA GeForce RTX 4090"

# Skip automatic SSH setup
./runpod-cli.py up --no-ssh
```

### status
Check current pod status and SSH details

```bash
# Show current pod
./runpod-cli.py status

# Show all your pods
./runpod-cli.py status --all
```

### down
Terminate a pod

```bash
# Terminate current pod
./runpod-cli.py down

# Terminate by pod ID
./runpod-cli.py down abc123xyz

# Terminate by name
./runpod-cli.py down gpu-workspace
```

### ssh
Manually configure SSH access (usually automatic)

```bash
./runpod-cli.py ssh
```

### gpus
List available GPUs with pricing

```bash
./runpod-cli.py gpus
```

Shows all NVIDIA GPUs, marking which are currently available with pricing per hour.

### install
Copy local setup script to pod

```bash
./runpod-cli.py install /path/to/setup.sh
```

Copies your setup script to `/workspace/setup.sh` on the pod and optionally runs it immediately.

## Setup Scripts

The tool supports two-stage setup automation:

1. **setup.sh** - Main system setup (runs first)
2. **post-setup.sh** - Custom project setup (runs after setup.sh, optional)

### Main Setup Script (setup.sh)

The main setup script runs automatically when a pod starts and handles:
- Auto-detecting Python version (3.9, 3.10, 3.11)
- Auto-detecting CUDA version and configuring environment
- Installing system packages
- Creating SSH keys for Git
- Setting up global Python virtual environment at `/opt/venv`
- Installing packages from `/workspace/packages.txt` if present

#### CUDA Environment

The setup script automatically:
- Detects installed CUDA version (11.x, 12.x, 13.x)
- Finds PyTorch CUDA libraries for TensorFlow compatibility
- Sets `LD_LIBRARY_PATH`, `CUDA_HOME`, and `PATH`
- Persists environment variables in `.bashrc`

This ensures GPU libraries work correctly with TensorFlow, PyTorch, and other frameworks across different pod instances.

### Post-Setup Script (post-setup.sh)

The post-setup script is **optional** and runs after the main setup completes. Use it for:
- Reinstalling Python packages in project virtual environments
- Cloning or updating Git repositories
- Running project-specific initialization
- Custom configurations

#### Example post-setup.sh

```bash
#!/bin/bash
# Post-Setup Script
# Place at: /workspace/post-setup.sh
# Make executable: chmod +x /workspace/post-setup.sh

echo "Running post-setup..."

# Reinstall packages for a specific project
PROJECT_VENV="/workspace/projects/my-project/venv"
PROJECT_REQUIREMENTS="/workspace/projects/my-project/requirements.txt"

if [ -f "$PROJECT_REQUIREMENTS" ] && [ -d "$PROJECT_VENV" ]; then
    echo "Reinstalling packages for my-project..."
    /workspace/pip-install-cached.sh "$PROJECT_VENV" "$PROJECT_REQUIREMENTS"
fi

# Auto-reinstall all project venvs
for project_dir in /workspace/projects/*/; do
    if [ -f "$project_dir/requirements.txt" ]; then
        venv_dir=$(find "$project_dir" -maxdepth 1 -type d -name "*venv*" | head -1)
        if [ -n "$venv_dir" ]; then
            echo "Reinstalling packages for: $(basename $project_dir)"
            /workspace/pip-install-cached.sh "$venv_dir" "$project_dir/requirements.txt"
        fi
    fi
done

# Clone repositories if they don't exist
if [ ! -d /workspace/projects/my-repo ]; then
    echo "Cloning repository..."
    git clone git@github.com:username/my-repo.git /workspace/projects/my-repo
fi

#!/bin/bash

echo "Running post-setup..."

# Reinstall packages from cache
PROJECT_VENV="/workspace/projects/projects-venv-963e4f9286"
PROJECT_REQUIREMENTS="/workspace/projects/2025-26b-fai2-adsai-AaronCiuffo245484/requirements.txt"

if [ -f "$PROJECT_REQUIREMENTS" ] && [ -d "$PROJECT_VENV" ]; then
    echo "Reinstalling packages..."
    /workspace/pip-install-cached.sh "$PROJECT_VENV" "$PROJECT_REQUIREMENTS"
fi

# Reinstall editable packages
source "$PROJECT_VENV/bin/activate"

echo "Reinstalling editable packages..."
pip install -e /workspace/projects/my-library-1
pip install -e /workspace/projects/my-library-2
# Add all your editable installs here


echo "Post-setup complete!"
```

### Custom Packages

Create `/workspace/packages.txt` on your pod to install additional apt packages:

```txt
# Additional packages
ffmpeg
libsm6
libxext6
build-essential
```

The setup script will automatically install these packages when it runs.

## Cached Package Installation

### The Problem

When you restart a pod (even with the same Docker image), you get assigned to a different physical host with potentially different CUDA drivers. This causes Python packages with compiled binaries (like TensorFlow) to break, requiring reinstallation.

### The Solution: pip-install-cached.sh

This script caches package wheels on your persistent volume and reinstalls them quickly on each pod start:

```bash
./pip-install-cached.sh <venv_path> <requirements_file> [cache_dir]
```

**Arguments:**
- `venv_path` - Absolute path to virtual environment (e.g., `/workspace/projects/my-project/venv`)
- `requirements_file` - Path to requirements.txt
- `cache_dir` - Optional cache directory (default: `/workspace/pip-cache`)

**Example:**
```bash
# First run: downloads packages to cache (~1-2 minutes for 32GB of packages)
/workspace/pip-install-cached.sh \
  /workspace/projects/ml-project/venv \
  /workspace/projects/ml-project/requirements.txt

# Subsequent runs: installs from cache (~30 seconds)
```

**How it works:**
1. **First run**: Downloads all wheels to `/workspace/pip-cache`
2. **Subsequent runs**: Installs from local cache (no network needed)
3. **Ensures compatibility**: Packages are still compiled for the current host's CUDA/system libraries
4. **Smart updating**: Automatically downloads missing packages if requirements change

### Workflow with Cached Installation

1. **Create your project structure:**
```bash
/workspace/
├── pip-cache/              # Shared cache (auto-created)
├── projects/
│   ├── project-a/
│   │   ├── venv/
│   │   └── requirements.txt
│   └── project-b/
│       ├── venv/
│       └── requirements.txt
└── post-setup.sh          # Auto-reinstalls all venvs
```

2. **First time setup:**
```bash
# Create venv
python3 -m venv /workspace/projects/my-project/venv

# Install packages (creates cache)
/workspace/pip-install-cached.sh \
  /workspace/projects/my-project/venv \
  /workspace/projects/my-project/requirements.txt
```

3. **Automatic reinstall on pod restart:**

Add to your `/workspace/post-setup.sh`:
```bash
#!/bin/bash
for project_dir in /workspace/projects/*/; do
    if [ -f "$project_dir/requirements.txt" ]; then
        venv_dir=$(find "$project_dir" -maxdepth 1 -type d -name "*venv*" | head -1)
        if [ -n "$venv_dir" ]; then
            /workspace/pip-install-cached.sh "$venv_dir" "$project_dir/requirements.txt"
        fi
    fi
done
```

This automatically reinstalls all your project venvs on every pod start, ensuring GPU compatibility while staying fast (~30 seconds vs 10+ minutes).

## SSH Key Management

The setup script creates persistent SSH keys in `/workspace/ssh` that survive pod restarts.

### First Time Setup

1. Start a pod with the setup script configured
2. The script will generate SSH keys and display the public key
3. Add the public key to your Git hosting service:
   - **GitHub**: https://github.com/settings/keys
   - **GitLab**: https://gitlab.com/-/profile/keys
   - **Bitbucket**: https://bitbucket.org/account/settings/ssh-keys/

### Subsequent Runs

The setup script detects existing keys and tests if they're registered with Git services. It only prompts for key installation if needed.

### Using Git on the Pod

Once keys are configured:

```bash
ssh runpod
git clone git@github.com:username/repo.git
```

## Network Volumes

Network volumes provide persistent storage across pod restarts and terminations.

### Benefits
- Data persists when pods are stopped/started
- SSH keys, code, and data survive across sessions
- Package cache speeds up pod initialization
- Faster pod startup (no need to re-download packages)

### Recommended Volume Structure

```
/workspace/
├── ssh/                   # SSH keys (auto-created by setup.sh)
│   ├── id_ed25519
│   └── id_ed25519.pub
├── pip-cache/             # Cached Python packages (auto-created)
├── packages.txt           # Additional apt packages to install
├── setup.sh               # Main setup script
├── post-setup.sh          # Custom post-setup script
├── pip-install-cached.sh  # Package installation helper
├── projects/              # Your code/projects
│   ├── project-a/
│   │   ├── venv/         # Project-specific venv
│   │   ├── requirements.txt
│   │   └── src/
│   └── project-b/
│       ├── venv/
│       ├── requirements.txt
│       └── notebooks/
├── datasets/              # Your datasets
└── models/                # Trained models
```

## Workflow Examples

### Quick Development Session

```bash
# Start a pod
./runpod-cli.py up

# Connect and work
ssh runpod
cd /workspace/projects/my-project
source venv/bin/activate
python train.py

# When done, terminate
exit
./runpod-cli.py down
```

### First Time Project Setup

```bash
# Start pod
./runpod-cli.py up
ssh runpod

# Create project structure
mkdir -p /workspace/projects/ml-project
cd /workspace/projects/ml-project

# Create venv
python3 -m venv venv

# Create requirements.txt
cat > requirements.txt <<EOF
tensorflow==2.13.0
numpy
pandas
matplotlib
jupyter
EOF

# Install with caching (first time is slower)
/workspace/pip-install-cached.sh \
  /workspace/projects/ml-project/venv \
  /workspace/projects/ml-project/requirements.txt

# Add to post-setup for auto-reinstall
# (Edit /workspace/post-setup.sh as shown above)
```

### Subsequent Pod Restarts

```bash
# Terminate old pod
./runpod-cli.py down

# Start new pod (might be different host)
./runpod-cli.py up

# Packages auto-reinstall from cache via post-setup.sh
# Takes ~30 seconds instead of 10+ minutes

# Connect and continue working
ssh runpod
cd /workspace/projects/ml-project
source venv/bin/activate
python train.py  # GPU works correctly!
```

### Try Different GPU

```bash
# Check available GPUs
./runpod-cli.py gpus

# Start with specific GPU
./runpod-cli.py up --gpu "NVIDIA A100 80GB PCIe"
```

### Managing Multiple Pods

```bash
# List all your pods
./runpod-cli.py status --all

# Terminate specific pod
./runpod-cli.py down old-pod-name
```

### Update Setup Scripts

```bash
# Edit local setup script
vim setup.sh

# Install to running pod
./runpod-cli.py install setup.sh

# Run it immediately
ssh runpod "bash /workspace/setup.sh"
```

## Configuration File

Settings are stored in `~/.runpod-config`:

```bash
RUNPOD_API_KEY="your_api_key"
RUNPOD_VOLUME_ID="v1l0yr2bgz"
RUNPOD_GPU_TYPE="NVIDIA GeForce RTX 3090"
RUNPOD_DOCKER_IMAGE="runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
RUNPOD_SETUP_SCRIPT="setup.sh"
RUNPOD_AUTO_SSH="true"
RUNPOD_POD_ID="current_pod_id"  # Updated automatically
```

You can manually edit this file or run `./runpod-cli.py setup` to reconfigure.

## SSH Configuration

The tool creates SSH configuration in `~/.ssh/`:

```
~/.ssh/
├── config                    # Includes runpod.d/*.conf
├── runpod.d/
│   └── current.conf         # Dynamic pod connection info
└── known_hosts              # SSH host keys
```

The `Host runpod` entry is always up-to-date, so `ssh runpod` always connects to your current pod.

## Troubleshooting

### "No GPUs currently available"

GPU availability changes frequently. Try:
```bash
./runpod-cli.py gpus  # Check what's available
./runpod-cli.py up --gpu "different GPU type"
```

### TensorFlow/PyTorch can't find GPU after pod restart

This happens when packages were installed on a different host. Solution:
```bash
# Reinstall packages from cache
ssh runpod
cd /workspace/projects/your-project
/workspace/pip-install-cached.sh $(pwd)/venv $(pwd)/requirements.txt

# Or set up post-setup.sh to do this automatically
```

### Volume not mounted at /workspace

Terminate and restart the pod. The mount point is set at creation time:
```bash
./runpod-cli.py down
./runpod-cli.py up
```

### SSH key permission errors

The setup script should fix this, but if needed:
```bash
ssh runpod "chmod 600 ~/.ssh/id_ed25519"
```

### Setup script not running

1. Check it's configured: `cat ~/.runpod-config | grep SETUP_SCRIPT`
2. Manually install: `./runpod-cli.py install setup.sh`
3. Run manually: `ssh runpod "bash /workspace/setup.sh"`

### Post-setup script not running

1. Check it exists and is executable:
```bash
ssh runpod "ls -la /workspace/post-setup.sh"
```
2. Make it executable:
```bash
ssh runpod "chmod +x /workspace/post-setup.sh"
```
3. Run manually:
```bash
ssh runpod "bash /workspace/post-setup.sh"
```

### Package cache taking too much space

Check cache size and clean if needed:
```bash
ssh runpod "du -sh /workspace/pip-cache"

# Remove old cached packages
ssh runpod "rm -rf /workspace/pip-cache"
# Cache will rebuild on next install
```

## Tips

- **Use network volumes** for any work you want to keep
- **Check GPU prices** with `./runpod-cli.py gpus` before starting
- **Use pip-install-cached.sh** for all package installations to save time on restarts
- **Set up post-setup.sh** once to automate venv reinstallation
- **Keep cache on volume** - one cache serves all your projects
- **Customize setup.sh** for your specific workflow
- **Use packages.txt** to install additional system packages
- **The global venv at /opt/venv activates automatically** when you SSH in
- **Create project-specific venvs** in `/workspace/projects/*/` for isolation

## Advanced Usage

### Custom Docker Images

During setup, choose option 3 to enter a custom image:
```
runpod/tensorflow:2.15.0-py3.11-cuda12.3.0-devel-ubuntu22.04
ghcr.io/username/custom-image:latest
```

**Note:** The setup script auto-detects Python and CUDA versions, so most images should work without modification.

### Multiple Configurations

Create different config files for different projects:
```bash
cp ~/.runpod-config ~/.runpod-config-project-a
cp ~/.runpod-config ~/.runpod-config-project-b

# Switch between them
cp ~/.runpod-config-project-a ~/.runpod-config
./runpod-cli.py up
```

### Sharing Setup Across Team

Keep your setup scripts in version control:
```bash
git add setup.sh post-setup.sh pip-install-cached.sh packages.txt
git commit -m "Add RunPod setup automation"
git push
```

Team members can clone and use the same setup:
```bash
./runpod-cli.py up
ssh runpod
git clone git@github.com:team/shared-setup.git /workspace/setup-scripts
cp /workspace/setup-scripts/*.sh /workspace/
```

## Performance Notes

### First Pod Start (Cold Start)
- Setup script: ~2-3 minutes
- Package installation: ~5-10 minutes (downloads + installs)
- Total: ~7-13 minutes

### Subsequent Pod Starts (Warm Start with Cache)
- Setup script: ~2-3 minutes
- Package installation from cache: ~30-60 seconds
- Total: ~3-4 minutes

### Time Savings
- Without cache: 10+ minutes per restart
- With cache: ~1 minute per restart
- **Savings: ~90% faster** for package installation

## Support

For issues or questions:
- Check RunPod documentation: https://docs.runpod.io/
- View pod logs in web console: https://www.runpod.io/console
- Verify API key is valid: https://www.runpod.io/console/user/settings

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

## Setup Script

The setup script (`setup.sh`) runs automatically when a pod starts (if configured). It handles:
- Installing system packages
- Creating SSH keys for Git
- Setting up Python virtual environment
- Custom package installation

### Using the Included Setup Script

The repository includes a ready-to-use `setup.sh` that:
- Updates apt cache (if >15 days old)
- Installs common tools (vim, curl, wget, git, htop, tmux, less)
- Installs packages from `/workspace/packages.txt` if present
- Creates persistent SSH keys in `/workspace/ssh`
- Configures Git to use workspace SSH keys
- Creates global Python 3.11 virtual environment at `/opt/venv`

### Configure Setup Script

During `./runpod-cli.py setup`, provide the path to your setup script:

```bash
Enter path to setup script (leave blank to skip): ./setup.sh
```

### Install Setup Script to Pod

After starting a pod, install your setup script:

```bash
./runpod-cli.py install setup.sh
```

This copies it to `/workspace/setup.sh` where it will run on future pod starts.

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
- Faster pod startup (no need to reinstall everything)

### Volume Structure

Recommended structure for `/workspace`:
```
/workspace/
├── ssh/              # SSH keys (auto-created by setup script)
│   ├── id_ed25519
│   └── id_ed25519.pub
├── packages.txt      # Additional apt packages to install
├── setup.sh          # Setup script
├── projects/         # Your code/projects
├── datasets/         # Your datasets
└── models/           # Trained models
```

## Workflow Examples

### Quick Development Session

```bash
# Start a pod
./runpod-cli.py up

# Connect and work
ssh runpod
cd /workspace/projects
git clone git@github.com:username/repo.git
cd repo
source /opt/venv/bin/activate
python train.py

# When done, terminate
exit
./runpod-cli.py down
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

### Update Setup Script

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

### Can't connect to other SSH hosts after using tool

The tool adds an `Include` directive to your `~/.ssh/config`. If you have connection issues, check that `~/.ssh/runpod.d/current.conf` contains a proper `Host runpod` block and not just bare `HostName`/`Port` directives.

## Tips

- **Use network volumes** for any work you want to keep
- **Check GPU prices** with `./runpod-cli.py gpus` before starting
- **Customize setup.sh** for your specific workflow
- **Use packages.txt** to install additional system packages
- **Keep setup.sh in version control** and share with team
- **The venv activates automatically** when you SSH in

## Advanced Usage

### Custom Docker Images

During setup, choose option 3 to enter a custom image:
```
runpod/tensorflow:2.15.0-py3.11-cuda12.3.0-devel-ubuntu22.04
ghcr.io/username/custom-image:latest
```

### Multiple Configurations

Create different config files for different projects:
```bash
cp ~/.runpod-config ~/.runpod-config-project-a
cp ~/.runpod-config ~/.runpod-config-project-b

# Switch between them
cp ~/.runpod-config-project-a ~/.runpod-config
./runpod-cli.py up
```

## Support

For issues or questions:
- Check RunPod documentation: https://docs.runpod.io/
- View pod logs in web console: https://www.runpod.io/console
- Verify API key is valid: https://www.runpod.io/console/user/settings
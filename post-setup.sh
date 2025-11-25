#!/bin/bash
# Post-Setup Script - Runs after main setup.sh completes
# Place this at: /workspace/post-setup.sh
# Make executable: chmod +x /workspace/post-setup.sh

echo ""
echo "=========================================="
echo "Post-Setup Script"
echo "=========================================="
echo ""
echo "This script runs automatically after setup.sh completes."
echo "Use it to:"
echo "  - Reinstall Python packages in project venvs"
echo "  - Clone or update git repositories"
echo "  - Run project-specific initialization"
echo "  - Set up custom configurations"
echo ""
echo "Example: Reinstall packages from cached requirements"
echo "  /workspace/pip-install-cached.sh /path/to/venv /path/to/requirements.txt"
echo ""
echo "Example: Clone a repository"
echo "  git clone git@github.com:username/repo.git /workspace/projects/repo"
echo ""
echo "Example: Auto-reinstall all project venvs"
echo "  for project_dir in /workspace/projects/*/; do"
echo "      # Find requirements.txt and venv, then reinstall"
echo "  done"
echo ""
echo "=========================================="
echo "Add your custom setup commands below this line"
echo "=========================================="
echo ""

# Your custom commands here

echo "Post-setup complete!"
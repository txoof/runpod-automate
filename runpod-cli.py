#!/usr/bin/env python3
"""runpod - Unified RunPod GPU management tool"""
import runpod
import os
import sys
import time
import argparse

VERSION = "1.0"
PROGRAM_NAME = os.path.basename(sys.argv[0])
CONFIG_FILE = os.path.expanduser("~/.runpod-config")

def load_config():
    """Load configuration from file"""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: No configuration found. Run '{PROGRAM_NAME} setup' first")
        sys.exit(1)
    
    config = {}
    with open(CONFIG_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value.strip('"')
    
    # Default AUTO_SSH to true if not set
    if 'RUNPOD_AUTO_SSH' not in config:
        config['RUNPOD_AUTO_SSH'] = 'true'
    
    return config

def setup_ssh_access(pod_id):
    """Configure SSH access for a pod using Include pattern"""
    ssh_dir = os.path.expanduser("~/.ssh")
    runpod_dir = os.path.join(ssh_dir, "runpod.d")
    current_conf = os.path.join(runpod_dir, "current.conf")
    ssh_config = os.path.join(ssh_dir, "config")
    known_hosts = os.path.join(ssh_dir, "known_hosts")
    
    # Ensure directories exist
    os.makedirs(runpod_dir, exist_ok=True)
    os.makedirs(ssh_dir, exist_ok=True)
    
    try:
        pod = runpod.get_pod(pod_id)
        
        if not pod:
            print(f"Pod {pod_id} not found")
            return False
        
        runtime = pod.get('runtime')
        if not runtime:
            print("Pod is not running yet")
            return False
        
        ports = runtime.get('ports', [])
        ssh_port = None
        ssh_host = None
        
        for port in ports:
            if port.get('privatePort') == 22:
                ssh_host = port.get('ip')
                ssh_port = port.get('publicPort')
                break
        
        if not ssh_host or not ssh_port:
            print("SSH port not found")
            return False
        
        # Write current.conf
        with open(current_conf, 'w') as f:
            f.write(f"HostName {ssh_host}\n")
            f.write(f"Port {ssh_port}\n")
        os.chmod(current_conf, 0o600)
        
        # Ensure main config has Include and Host runpod entry
        include_line = f"Include {runpod_dir}/*.conf\n"
        host_block = "\nHost runpod\n  User root\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null\n"
        
        config_needs_update = True
        if os.path.exists(ssh_config):
            with open(ssh_config, 'r') as f:
                content = f.read()
                if include_line.strip() in content and "Host runpod" in content:
                    config_needs_update = False
        
        if config_needs_update:
            # Add Include at top and Host block
            existing_content = ""
            if os.path.exists(ssh_config):
                with open(ssh_config, 'r') as f:
                    existing_content = f.read()
            
            with open(ssh_config, 'w') as f:
                # Include must be at the top
                if include_line.strip() not in existing_content:
                    f.write(include_line)
                
                f.write(existing_content)
                
                # Add Host block if not present
                if "Host runpod" not in existing_content:
                    f.write(host_block)
        
        # Refresh known_hosts
        import subprocess
        
        # Remove old entries
        subprocess.run(['ssh-keygen', '-R', ssh_host], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['ssh-keygen', '-R', f'[{ssh_host}]:{ssh_port}'], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Scan new keys
        result = subprocess.run(
            ['ssh-keyscan', '-p', str(ssh_port), '-t', 'ed25519,rsa', ssh_host],
            capture_output=True, text=True
        )
        
        if result.returncode == 0 and result.stdout:
            # Format as [ip]:port
            new_keys = result.stdout.replace(f"{ssh_host} ", f"[{ssh_host}]:{ssh_port} ")
            
            with open(known_hosts, 'a') as f:
                f.write(new_keys)
            os.chmod(known_hosts, 0o600)
            
            print(f"Updated {current_conf}")
            print(f"Refreshed host key for [{ssh_host}]:{ssh_port}")
        
        print("You can now connect with: ssh runpod")
        return True
        
    except Exception as e:
        print(f"Error setting up SSH: {e}")
        return False

def cmd_up(args):
    """Start a GPU pod"""
    config = load_config()
    runpod.api_key = config['RUNPOD_API_KEY']
    
    print("Starting RunPod instance...")
    print(f"  GPU: {config['RUNPOD_GPU_TYPE']}")
    print(f"  Image: {config['RUNPOD_DOCKER_IMAGE']}")
    if config.get('RUNPOD_VOLUME_ID'):
        print(f"  Volume: {config['RUNPOD_VOLUME_ID']}")
    print()
    
    try:
        pod_args = {
            'name': "gpu-workspace",
            'image_name': config['RUNPOD_DOCKER_IMAGE'],
            'gpu_type_id': config['RUNPOD_GPU_TYPE'],
            'container_disk_in_gb': 20,
            'ports': "8888/http,22/tcp"
        }
        
        if config.get('RUNPOD_VOLUME_ID'):
            pod_args['network_volume_id'] = config['RUNPOD_VOLUME_ID']
        
        pod = runpod.create_pod(**pod_args)
        
        print("Pod created successfully")
        print(f"Pod ID: {pod['id']}")
        
        # Save pod ID
        with open(CONFIG_FILE, 'a') as f:
            f.write(f'\nRUNPOD_POD_ID="{pod["id"]}"\n')
        
        # Wait for pod to start with progress bar
        pod_id = pod['id']
        max_wait = 300  # 5 minutes max
        check_interval = 2  # Check every 2 seconds
        elapsed = 0
        bar_width = 40
        
        while elapsed < max_wait:
            time.sleep(check_interval)
            elapsed += check_interval
            
            # Check if running
            pod_status = runpod.get_pod(pod_id)
            if pod_status and pod_status.get('runtime'):
                # Clear line and show success
                print(f"\r{'=' * bar_width} Ready!          ")
                break
            
            # Draw progress bar
            progress = elapsed / max_wait
            filled = int(bar_width * progress)
            bar = '=' * filled + '-' * (bar_width - filled)
            remaining = int(max_wait - elapsed)
            print(f"\rStarting pod [{bar}] {remaining}s ", end='', flush=True)
        else:
            print(f"\r{'=' * bar_width} Timeout         ")
            print("Pod may still be starting")
            return
        
        # Auto-configure SSH unless --no-ssh flag is set
        auto_ssh = config.get('RUNPOD_AUTO_SSH', 'true').lower() == 'true'
        
        if args.no_ssh:
            print(f"\nSSH setup skipped (--no-ssh flag)")
            print(f"Run '{PROGRAM_NAME} ssh' to configure SSH access")
        elif auto_ssh:
            print("\nConfiguring SSH access...")
            setup_ssh_access(pod_id)
        else:
            print(f"\nRun '{PROGRAM_NAME} ssh' to configure SSH access")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_status():
    """Check pod status"""
    config = load_config()
    
    if 'RUNPOD_POD_ID' not in config:
        print("No active pod found")
        sys.exit(0)
    
    runpod.api_key = config['RUNPOD_API_KEY']
    pod_id = config['RUNPOD_POD_ID']
    
    try:
        pod = runpod.get_pod(pod_id)
        
        if not pod:
            print(f"Pod {pod_id} not found")
            sys.exit(1)
        
        print(f"Pod ID: {pod['id']}")
        print(f"Name: {pod['name']}")
        print(f"Image: {pod['imageName']}")
        
        runtime = pod.get('runtime')
        if runtime:
            print("Status: Running")
            
            # Get SSH details
            ports = runtime.get('ports', [])
            for port in ports:
                if port.get('privatePort') == 22:
                    print(f"\nSSH: ssh root@{port['ip']} -p {port['publicPort']}")
                    break
        else:
            print("Status: Not running")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_down():
    """Stop/terminate pod"""
    config = load_config()
    
    if 'RUNPOD_POD_ID' not in config:
        print("No active pod found")
        sys.exit(0)
    
    runpod.api_key = config['RUNPOD_API_KEY']
    pod_id = config['RUNPOD_POD_ID']
    
    try:
        pod = runpod.get_pod(pod_id)
        
        if not pod:
            print(f"Pod {pod_id} not found (may already be terminated)")
        else:
            print(f"Terminating pod {pod_id}...")
            runpod.terminate_pod(pod_id)
            
            # Wait and verify termination with progress bar
            max_wait = 30  # 30 seconds max
            check_interval = 0.5  # Check every 0.5 seconds
            elapsed = 0
            bar_width = 40
            
            while elapsed < max_wait:
                time.sleep(check_interval)
                elapsed += check_interval
                
                # Check if terminated
                pod_status = runpod.get_pod(pod_id)
                if not pod_status:
                    # Clear line and show success
                    print(f"\r{'=' * bar_width} Confirmed!     ")
                    break
                
                # Draw progress bar
                progress = elapsed / max_wait
                filled = int(bar_width * progress)
                bar = '=' * filled + '-' * (bar_width - filled)
                remaining = int(max_wait - elapsed)
                print(f"\rVerifying [{bar}] {remaining}s ", end='', flush=True)
            else:
                print(f"\r{'=' * bar_width} Timeout         ")
                print("Pod may still be terminating")
        
        # Remove pod ID from config
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()
        
        with open(CONFIG_FILE, 'w') as f:
            for line in lines:
                if not line.startswith('RUNPOD_POD_ID='):
                    f.write(line)
        
        print("\nPod ID removed from config")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_ssh():
    """Configure SSH access"""
    config = load_config()
    
    if 'RUNPOD_POD_ID' not in config:
        print(f"No active pod found. Run '{PROGRAM_NAME} up' first")
        sys.exit(1)
    
    runpod.api_key = config['RUNPOD_API_KEY']
    pod_id = config['RUNPOD_POD_ID']
    
    setup_ssh_access(pod_id)

def usage():
    """Print usage information"""
    print(f"{PROGRAM_NAME} v{VERSION} - RunPod GPU management tool")
    print()
    print(f"Usage: {PROGRAM_NAME} <command> [options]")
    print()
    print("Commands:")
    print("  up       Start a GPU pod")
    print("  status   Check pod status and get SSH details")
    print("  down     Stop/terminate the pod")
    print("  ssh      Configure SSH access (updates ~/.ssh/config)")
    print()
    print("Options:")
    print("  --no-ssh    Don't auto-configure SSH (for 'up' command)")
    print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RunPod GPU management tool", add_help=False)
    parser.add_argument('command', nargs='?', help='Command to run')
    parser.add_argument('--no-ssh', action='store_true', help="Don't auto-configure SSH")
    
    args = parser.parse_args()
    
    if not args.command:
        usage()
        sys.exit(1)
    
    command = args.command
    
    if command == "up":
        cmd_up(args)
    elif command == "status":
        cmd_status()
    elif command == "down":
        cmd_down()
    elif command == "ssh":
        cmd_ssh()
    else:
        print(f"Unknown command: {command}")
        print()
        usage()
        sys.exit(1)
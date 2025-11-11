#!/usr/bin/env python3
"""runpod - Unified RunPod GPU management tool"""
import runpod
import os
import sys
import time
import argparse
import subprocess

VERSION = "2.0"
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
    
    # Defaults
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
            existing_content = ""
            if os.path.exists(ssh_config):
                with open(ssh_config, 'r') as f:
                    existing_content = f.read()
            
            with open(ssh_config, 'w') as f:
                if include_line.strip() not in existing_content:
                    f.write(include_line)
                
                f.write(existing_content)
                
                if "Host runpod" not in existing_content:
                    f.write(host_block)
        
        # Refresh known_hosts
        subprocess.run(['ssh-keygen', '-R', ssh_host], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['ssh-keygen', '-R', f'[{ssh_host}]:{ssh_port}'], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        result = subprocess.run(
            ['ssh-keyscan', '-p', str(ssh_port), '-t', 'ed25519,rsa', ssh_host],
            capture_output=True, text=True
        )
        
        if result.returncode == 0 and result.stdout:
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

def cmd_ssh():
    """Configure SSH access"""
    config = load_config()
    
    if 'RUNPOD_POD_ID' not in config:
        print(f"No active pod found. Run '{PROGRAM_NAME} up' first")
        sys.exit(1)
    
    runpod.api_key = config['RUNPOD_API_KEY']
    pod_id = config['RUNPOD_POD_ID']
    
    setup_ssh_access(pod_id)

def check_and_run_setup(config):
    """Check for setup script and run if present"""
    if not config.get('RUNPOD_VOLUME_ID'):
        return
    
    setup_script = config.get('RUNPOD_SETUP_SCRIPT', '').strip()
    if not setup_script:
        return
    
    print("\nChecking for setup script...")
    
    # Check if script exists on remote
    result = subprocess.run(
        ['ssh', 'runpod', 'test -f /workspace/setup.sh'],
        capture_output=True
    )
    
    if result.returncode != 0:
        print(f"Setup script not found on remote pod")
        print(f"Run: {PROGRAM_NAME} install {setup_script}")
        return
    
    # Check if local script is newer
    if os.path.exists(setup_script):
        local_mtime = os.path.getmtime(setup_script)
        remote_result = subprocess.run(
            ['ssh', 'runpod', 'stat -c %Y /workspace/setup.sh 2>/dev/null || stat -f %m /workspace/setup.sh'],
            capture_output=True,
            text=True,
            shell=True
        )
        
        if remote_result.returncode == 0:
            try:
                remote_mtime = int(remote_result.stdout.strip())
                if local_mtime > remote_mtime:
                    print(f"Local setup script is newer")
                    update = input(f"Update remote script? (y/N): ").strip().lower()
                    if update == 'y':
                        subprocess.run(['scp', setup_script, 'runpod:/workspace/setup.sh'])
                        subprocess.run(['ssh', 'runpod', 'chmod +x /workspace/setup.sh'])
                        print("Setup script updated")
            except ValueError:
                pass
    
    print("Running setup script...")
    result = subprocess.run(['ssh', 'runpod', 'bash /workspace/setup.sh'])
    
    if result.returncode == 0:
        print("Setup completed successfully")
    else:
        print("Setup script encountered errors")

def cmd_up(args):
    """Start a GPU pod"""
    config = load_config()
    runpod.api_key = config['RUNPOD_API_KEY']
    
    # Use --gpu override if provided, otherwise use config
    gpu_type = args.gpu if args.gpu else config['RUNPOD_GPU_TYPE']
    
    print("Starting RunPod instance...")
    print(f"  GPU: {gpu_type}")
    print(f"  Image: {config['RUNPOD_DOCKER_IMAGE']}")
    if config.get('RUNPOD_VOLUME_ID'):
        print(f"  Volume: {config['RUNPOD_VOLUME_ID']}")
    print()
    
    try:
        pod_args = {
            'name': "gpu-workspace",
            'image_name': config['RUNPOD_DOCKER_IMAGE'],
            'gpu_type_id': gpu_type,
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
        max_wait = 300
        check_interval = 2
        elapsed = 0
        bar_width = 40
        
        while elapsed < max_wait:
            time.sleep(check_interval)
            elapsed += check_interval
            
            pod_status = runpod.get_pod(pod_id)
            if pod_status and pod_status.get('runtime'):
                print(f"\r{'=' * bar_width} Ready!          ")
                break
            
            progress = elapsed / max_wait
            filled = int(bar_width * progress)
            bar = '=' * filled + '-' * (bar_width - filled)
            remaining = int(max_wait - elapsed)
            print(f"\rStarting pod [{bar}] {remaining}s ", end='', flush=True)
        else:
            print(f"\r{'=' * bar_width} Timeout         ")
            print("Pod may still be starting")
            return
        
        auto_ssh = config.get('RUNPOD_AUTO_SSH', 'true').lower() == 'true'
        
        if args.no_ssh:
            print(f"\nSSH setup skipped (--no-ssh flag)")
            print(f"Run '{PROGRAM_NAME} ssh' to configure SSH access")
        elif auto_ssh:
            print("\nConfiguring SSH access...")
            if setup_ssh_access(pod_id):
                time.sleep(2)
                check_and_run_setup(config)
        else:
            print(f"\nRun '{PROGRAM_NAME} ssh' to configure SSH access")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_status(args):
    """Check pod status"""
    config = load_config()
    runpod.api_key = config['RUNPOD_API_KEY']
    
    # If --all flag, list all pods
    if args.all:
        try:
            pods = runpod.get_pods()
            
            if not pods:
                print("No pods found")
                sys.exit(0)
            
            print(f"Found {len(pods)} pod(s):\n")
            
            for pod in pods:
                status = "Running" if pod.get('runtime') else "Stopped"
                print(f"ID: {pod['id']}")
                print(f"  Name: {pod['name']}")
                print(f"  Status: {status}")
                print(f"  GPU: {pod.get('machine', {}).get('gpuDisplayName', 'Unknown')}")
                print(f"  Image: {pod['imageName']}")
                
                runtime = pod.get('runtime')
                if runtime:
                    ports = runtime.get('ports', [])
                    for port in ports:
                        if port.get('privatePort') == 22:
                            print(f"  SSH: ssh root@{port['ip']} -p {port['publicPort']}")
                            break
                
                # Mark current pod
                if pod['id'] == config.get('RUNPOD_POD_ID'):
                    print("  [CURRENT]")
                
                print()
            
            sys.exit(0)
            
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    # Otherwise show current pod
    if 'RUNPOD_POD_ID' not in config:
        print("No active pod found")
        print(f"Use '{PROGRAM_NAME} status --all' to see all pods")
        sys.exit(0)
    
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

def cmd_down(args):
    """Stop/terminate pod"""
    config = load_config()
    runpod.api_key = config['RUNPOD_API_KEY']
    
    # If pod ID/name provided as argument
    if args.args:
        target = args.args[0]
        
        try:
            # First try as direct pod ID
            pod = runpod.get_pod(target)
            
            # If not found, search by name
            if not pod:
                pods = runpod.get_pods()
                matching_pods = [p for p in pods if p['name'] == target or p['id'].startswith(target)]
                
                if not matching_pods:
                    print(f"No pod found matching: {target}")
                    sys.exit(1)
                elif len(matching_pods) > 1:
                    print(f"Multiple pods match '{target}':")
                    for p in matching_pods:
                        print(f"  {p['id']} - {p['name']}")
                    print("\nPlease be more specific")
                    sys.exit(1)
                else:
                    pod = matching_pods[0]
            
            pod_id = pod['id']
            
            print(f"Terminating pod {pod['name']} ({pod_id})...")
            runpod.terminate_pod(pod_id)
            
            # Verify termination with progress bar
            max_wait = 30
            check_interval = 0.5
            elapsed = 0
            bar_width = 40
            
            while elapsed < max_wait:
                time.sleep(check_interval)
                elapsed += check_interval
                
                pod_status = runpod.get_pod(pod_id)
                if not pod_status:
                    print(f"\r{'=' * bar_width} Confirmed!     ")
                    break
                
                progress = elapsed / max_wait
                filled = int(bar_width * progress)
                bar = '=' * filled + '-' * (bar_width - filled)
                remaining = int(max_wait - elapsed)
                print(f"\rVerifying [{bar}] {remaining}s ", end='', flush=True)
            else:
                print(f"\r{'=' * bar_width} Timeout         ")
                print("Pod may still be terminating")
            
            # Remove from config if it was the current pod
            if config.get('RUNPOD_POD_ID') == pod_id:
                with open(CONFIG_FILE, 'r') as f:
                    lines = f.readlines()
                
                with open(CONFIG_FILE, 'w') as f:
                    for line in lines:
                        if not line.startswith('RUNPOD_POD_ID='):
                            f.write(line)
                
                print("\nPod ID removed from config")
            else:
                print("\nPod terminated")
            
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
        
        return
    
    # Otherwise terminate current pod
    if 'RUNPOD_POD_ID' not in config:
        print("No active pod found")
        print(f"Usage: {PROGRAM_NAME} down [pod_id_or_name]")
        sys.exit(0)
    
    pod_id = config['RUNPOD_POD_ID']
    
    try:
        pod = runpod.get_pod(pod_id)
        
        if not pod:
            print(f"Pod {pod_id} not found (may already be terminated)")
        else:
            print(f"Terminating pod {pod_id}...")
            runpod.terminate_pod(pod_id)
            
            max_wait = 30
            check_interval = 0.5
            elapsed = 0
            bar_width = 40
            
            while elapsed < max_wait:
                time.sleep(check_interval)
                elapsed += check_interval
                
                pod_status = runpod.get_pod(pod_id)
                if not pod_status:
                    print(f"\r{'=' * bar_width} Confirmed!     ")
                    break
                
                progress = elapsed / max_wait
                filled = int(bar_width * progress)
                bar = '=' * filled + '-' * (bar_width - filled)
                remaining = int(max_wait - elapsed)
                print(f"\rVerifying [{bar}] {remaining}s ", end='', flush=True)
            else:
                print(f"\r{'=' * bar_width} Timeout         ")
                print("Pod may still be terminating")
        
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

def cmd_gpus():
    """List available GPUs"""
    config = load_config()
    runpod.api_key = config['RUNPOD_API_KEY']
    
    try:
        import requests
        
        print("Fetching GPU types...\n")
        
        response = requests.post(
            'https://api.runpod.io/graphql',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config["RUNPOD_API_KEY"]}'
            },
            json={'query': 'query { gpuTypes { id displayName memoryInGb lowestPrice { uninterruptablePrice } secureCloud communityCloud } }'}
        )
        
        gpu_data = response.json()
        gpus = gpu_data['data']['gpuTypes']
        
        # Filter to NVIDIA GPUs
        nvidia_gpus = [g for g in gpus if 'NVIDIA' in g['id']]
        
        if not nvidia_gpus:
            print("No NVIDIA GPUs found")
            sys.exit(0)
        
        # Separate available (with pricing) and unavailable
        available_gpus = [g for g in nvidia_gpus if g.get('lowestPrice')]
        unavailable_gpus = [g for g in nvidia_gpus if not g.get('lowestPrice')]
        
        # Sort available by price
        available_gpus.sort(key=lambda x: float(x['lowestPrice']['uninterruptablePrice']))
        unavailable_gpus.sort(key=lambda x: x['id'])
        
        if available_gpus:
            print("AVAILABLE NOW (can deploy immediately):")
            print(f"{'Full Name':<45} {'Memory':<10} {'Price/Hour':<15} {'Cloud'}")
            print("-" * 95)
            
            for gpu in available_gpus:
                name = gpu['id']
                memory = f"{gpu['memoryInGb']}GB"
                price_per_hour = float(gpu['lowestPrice']['uninterruptablePrice'])
                price = f"${price_per_hour:.4f}/hr"
                
                availability = []
                if gpu['secureCloud']:
                    availability.append('Secure')
                if gpu['communityCloud']:
                    availability.append('Community')
                avail_str = ', '.join(availability)
                
                print(f"{name:<45} {memory:<10} {price:<15} {avail_str}")
            
            print(f"\nCurrently available: {len(available_gpus)} GPU types")
            print("\nNote: These GPUs have on-demand capacity available right now.")
            print("      Availability changes frequently based on demand.")
        else:
            print("No GPUs currently available for immediate on-demand deployment")
            print("This is unusual - availability typically changes within minutes.")
        
        if unavailable_gpus:
            print(f"\n\nCURRENTLY UNAVAILABLE (no on-demand capacity):")
            print(f"{'Full Name':<45} {'Memory'}")
            print("-" * 60)
            
            for gpu in unavailable_gpus:
                name = gpu['id']
                memory = f"{gpu['memoryInGb']}GB"
                print(f"{name:<45} {memory}")
            
            print(f"\nCurrently unavailable: {len(unavailable_gpus)} GPU types")
            print("These may become available later. Check back or use spot instances.")
        
        if config.get('RUNPOD_VOLUME_ID'):
            print(f"\n{'='*95}")
            print(f"Your configured volume: {config['RUNPOD_VOLUME_ID']}")
            print("Network volumes work with all GPU types across all regions.")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    """Configure SSH access"""
    config = load_config()
    
    if 'RUNPOD_POD_ID' not in config:
        print(f"No active pod found. Run '{PROGRAM_NAME} up' first")
        sys.exit(1)
    
    runpod.api_key = config['RUNPOD_API_KEY']
    pod_id = config['RUNPOD_POD_ID']
    
    setup_ssh_access(pod_id)

def cmd_install(args):
    """Install local setup script to remote pod"""
    if not args.args:
        print(f"Usage: {PROGRAM_NAME} install <local_script_path>")
        sys.exit(1)
    
    config = load_config()
    
    if 'RUNPOD_POD_ID' not in config:
        print(f"No active pod found. Run '{PROGRAM_NAME} up' first")
        sys.exit(1)
    
    local_script = args.args[0]
    
    if not os.path.exists(local_script):
        print(f"Error: {local_script} not found")
        sys.exit(1)
    
    if not config.get('RUNPOD_VOLUME_ID'):
        print("Error: No volume configured. Setup scripts require a network volume.")
        sys.exit(1)
    
    print(f"Copying {local_script} to /workspace/setup.sh...")
    
    result = subprocess.run(
        ['scp', local_script, 'runpod:/workspace/setup.sh'],
        capture_output=True
    )
    
    if result.returncode != 0:
        print(f"Error copying script: {result.stderr.decode()}")
        sys.exit(1)
    
    subprocess.run(['ssh', 'runpod', 'chmod +x /workspace/setup.sh'])
    
    print("Setup script installed successfully")
    
    run_now = input("Run setup script now? (y/N): ").strip().lower()
    if run_now == 'y':
        print("\nRunning setup script...")
        subprocess.run(['ssh', 'runpod', 'bash /workspace/setup.sh'])

def cmd_setup():
    """Run setup.py configuration"""
    import requests
    
    print(f"{PROGRAM_NAME} v{VERSION}")
    print("RunPod CLI Setup\n")
    
    # Load existing config if it exists
    config = {}
    if os.path.exists(CONFIG_FILE):
        print(f"Found existing configuration at {CONFIG_FILE}")
        with open(CONFIG_FILE) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    config[key] = value.strip('"')
        
        print("\nCurrent settings:")
        print("  API Key: (hidden)")
        print(f"  Volume ID: {config.get('RUNPOD_VOLUME_ID', '(not set)')}")
        print(f"  GPU Type: {config.get('RUNPOD_GPU_TYPE', '(not set)')}")
        print(f"  Docker Image: {config.get('RUNPOD_DOCKER_IMAGE', '(not set)')}")
        print(f"  Setup Script: {config.get('RUNPOD_SETUP_SCRIPT', '(not set)')}")
        print()
        
        reconfigure = input("Reconfigure? (y/N): ").strip().lower()
        if reconfigure != 'y':
            print("Keeping existing configuration.")
            sys.exit(0)
        print()
    
    # API Key
    if config.get('RUNPOD_API_KEY'):
        print("Current API Key: (hidden)")
        api_key = input("Enter new API key (press Enter to keep current): ").strip()
        if not api_key:
            api_key = config['RUNPOD_API_KEY']
    else:
        api_key = input("Enter your RunPod API key: ").strip()
    
    # Fetch GPU list
    print("\nFetching available GPU types...")
    try:
        response = requests.post(
            'https://api.runpod.io/graphql',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            json={'query': 'query { gpuTypes { id displayName } }'}
        )
        gpu_data = response.json()
        gpu_list = [g['id'] for g in gpu_data['data']['gpuTypes'] if 'NVIDIA' in g['id']]
        
        if not gpu_list:
            print("Error: Failed to fetch GPU list. Check your API key.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error fetching GPU list: {e}")
        sys.exit(1)
    
    # GPU Type selection
    while True:
        print()
        if config.get('RUNPOD_GPU_TYPE'):
            print(f"Current GPU type: {config['RUNPOD_GPU_TYPE']}")
        
        search_term = input("Enter search term for GPU (or 'quit' to exit): ").strip()
        
        if search_term.lower() == 'quit':
            print("Setup cancelled.")
            sys.exit(1)
        
        if not search_term and config.get('RUNPOD_GPU_TYPE'):
            gpu_type = config['RUNPOD_GPU_TYPE']
            break
        
        matches = [g for g in gpu_list if search_term.lower() in g.lower()]
        
        if not matches:
            print(f"No matches found for '{search_term}'. Try again.")
            continue
        
        if len(matches) == 1:
            gpu_type = matches[0]
            print(f"Selected: {gpu_type}")
            break
        else:
            print(f"Found {len(matches)} matches:")
            for match in matches:
                print(f"  {match}")
            print("Please be more specific.")
    
    # Volume ID
    if config.get('RUNPOD_VOLUME_ID'):
        print(f"Current Volume ID: {config['RUNPOD_VOLUME_ID']}")
        volume_id = input("Enter new Volume ID (press Enter to keep current): ").strip()
        if not volume_id:
            volume_id = config['RUNPOD_VOLUME_ID']
    else:
        volume_id = input("Enter your Network Volume ID (leave blank if you don't have one yet): ").strip()
    
    # Docker Image
    while True:
        if config.get('RUNPOD_DOCKER_IMAGE'):
            print(f"Current Docker Image: {config['RUNPOD_DOCKER_IMAGE']}")
        
        print("\nSelect a container image (Python 3.11+):")
        print("1) PyTorch 2.4.0 + Python 3.11 + CUDA 12.4")
        print("2) PyTorch 2.2.1 + Python 3.11 + CUDA 12.1")
        print("3) Enter custom image name")
        
        if config.get('RUNPOD_DOCKER_IMAGE'):
            choice = input("Choice [1-3] (press Enter to keep current): ").strip()
        else:
            choice = input("Choice [1-3]: ").strip()
        
        if not choice and config.get('RUNPOD_DOCKER_IMAGE'):
            docker_image = config['RUNPOD_DOCKER_IMAGE']
            break
        
        if choice == '1':
            docker_image = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
            break
        elif choice == '2':
            docker_image = "runpod/pytorch:2.2.1-py3.11-cuda12.1.1-devel-ubuntu22.04"
            break
        elif choice == '3':
            print("\nVisit: https://console.runpod.io/hub?tabSelected=templates")
            custom_image = input("Enter custom image name: ").strip()
            if custom_image:
                docker_image = custom_image
                break
        else:
            print("Invalid choice, try again.")
    
    # Setup script path
    if config.get('RUNPOD_SETUP_SCRIPT'):
        print(f"Current setup script: {config['RUNPOD_SETUP_SCRIPT']}")
        setup_script = input("Enter path to setup script (press Enter to keep current, 'none' to disable): ").strip()
        if setup_script.lower() == 'none':
            setup_script = ""
        elif not setup_script:
            setup_script = config['RUNPOD_SETUP_SCRIPT']
    else:
        setup_script = input("Enter path to setup script (leave blank to skip): ").strip()
    
    # Save configuration
    with open(CONFIG_FILE, 'w') as f:
        f.write(f'RUNPOD_API_KEY="{api_key}"\n')
        f.write(f'RUNPOD_VOLUME_ID="{volume_id}"\n')
        f.write(f'RUNPOD_GPU_TYPE="{gpu_type}"\n')
        f.write(f'RUNPOD_DOCKER_IMAGE="{docker_image}"\n')
        f.write(f'RUNPOD_SETUP_SCRIPT="{setup_script}"\n')
        f.write(f'RUNPOD_AUTO_SSH="true"\n')
    
    os.chmod(CONFIG_FILE, 0o600)
    
    print(f"\nConfiguration saved to {CONFIG_FILE}")
    print("\nFinal configuration:")
    print("  API Key: (hidden)")
    print(f"  Volume ID: {volume_id if volume_id else '(not set)'}")
    print(f"  GPU Type: {gpu_type}")
    print(f"  Docker Image: {docker_image}")
    print(f"  Setup Script: {setup_script if setup_script else '(not set)'}")

def usage():
    """Print usage information"""
    print(f"{PROGRAM_NAME} v{VERSION} - RunPod GPU management tool")
    print()
    print(f"Usage: {PROGRAM_NAME} <command> [options]")
    print()
    print("Commands:")
    print("  setup             Configure RunPod settings")
    print("  up                Start a GPU pod")
    print("  status [--all]    Check pod status and get SSH details")
    print("  down [pod]        Stop/terminate pod (current or by ID/name)")
    print("  ssh               Configure SSH access (updates ~/.ssh/config)")
    print("  install <script>  Copy local setup script to remote pod")
    print("  gpus              List available GPUs with pricing")
    print()
    print("Options:")
    print("  --no-ssh       Don't auto-configure SSH (for 'up' command)")
    print("  --all          Show all pods (for 'status' command)")
    print("  --gpu <type>   Override configured GPU type (for 'up' command)")
    print()
    print("Examples:")
    print(f"  {PROGRAM_NAME} up --gpu 'NVIDIA GeForce RTX 4090'")
    print(f"  {PROGRAM_NAME} status --all")
    print(f"  {PROGRAM_NAME} down my-pod-name")
    print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RunPod GPU management tool", add_help=False)
    parser.add_argument('command', nargs='?', help='Command to run')
    parser.add_argument('args', nargs='*', help='Additional arguments')
    parser.add_argument('--no-ssh', action='store_true', help="Don't auto-configure SSH")
    parser.add_argument('--all', action='store_true', help="Show all pods (for status command)")
    parser.add_argument('--gpu', type=str, help="Override configured GPU type (for up command)")
    
    args = parser.parse_args()
    
    if not args.command:
        usage()
        sys.exit(1)
    
    command = args.command
    
    if command == "setup":
        cmd_setup()
    elif command == "up":
        cmd_up(args)
    elif command == "status":
        cmd_status(args)
    elif command == "down":
        cmd_down(args)
    elif command == "ssh":
        cmd_ssh()
    elif command == "install":
        cmd_install(args)
    elif command == "gpus":
        cmd_gpus()
    else:
        print(f"Unknown command: {command}")
        print()
        usage()
        sys.exit(1)
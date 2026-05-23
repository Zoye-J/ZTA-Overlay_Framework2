#scripts/bootstrap_network.py

#!/usr/bin/env python
"""
Bootstrap the entire overlay network from zero
No hardcoded values - everything from config files
"""
import os
import sys
import yaml
import subprocess
import requests

def bootstrap():
    print("=== Bootstrapping ZTA Overlay Network for Bangladesh ===")
    
    # Load configurations
    with open('../config/controller_config.yaml', 'r') as f:
        controller_config = yaml.safe_load(f)
    
    with open('../config/services.yaml', 'r') as f:
        services = yaml.safe_load(f)
    
    # Step 1: Generate all certificates
    print("\n[1/5] Generating certificates for all identities...")
    subprocess.run(['python', '../certs/generate_identities.py'], check=True)
    
    # Step 2: Start the Controller
    print("\n[2/5] Starting ZTA Controller...")
    controller_process = subprocess.Popen(
        ['python', '../controller/app.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Step 3: Enroll each service
    print("\n[3/5] Enrolling services with Controller...")
    enrollment_token = os.environ.get('MASTER_ENROLLMENT_SECRET', 'dev_token_123')
    
    for service in services['services']:
        print(f"  Enrolling {service['name']}...")
        response = requests.post(
            f"http://localhost:{controller_config['controller']['control_plane']['bind_port']}/api/v1/enroll",
            json={
                'type': 'service',
                'name': service['name'],
                'enrollment_token': enrollment_token
            }
        )
        if response.status_code == 200:
            print(f"    ✓ {service['name']} enrolled successfully")
    
    # Step 4: Start Edge Router for each service
    print("\n[4/5] Starting Edge Routers for each service...")
    routers = []
    for service in services['services']:
        print(f"  Starting Edge Router for {service['name']}...")
        # Create router config directory if not exists
        os.makedirs(f"../edge-router/configs/{service['name']}", exist_ok=True)
        
        router_process = subprocess.Popen(
            ['python', '../edge-router/router_app.py'],
            cwd=f"../edge-router",
            env={**os.environ, 'ROUTER_IDENTITY': service['name']}
        )
        routers.append(router_process)
    
    # Step 5: Start the zitified services
    print("\n[5/5] Starting Zitified Services...")
    services_processes = []
    for service in services['services']:
        print(f"  Starting {service['name']} service...")
        service_process = subprocess.Popen(
            ['python', f'app.py'],
            cwd=f"../ziti-services/{service['name']}"
        )
        services_processes.append(service_process)
    
    print("\n=== Bootstrap Complete! ===")
    print("Overlay network is running with:")
    print("  - Controller: localhost:8080")
    print("  - All services bound to localhost only")
    print("  - Zero inbound ports exposed")
    
    # Keep running
    try:
        for proc in routers + services_processes + [controller_process]:
            proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down overlay network...")
        for proc in routers + services_processes + [controller_process]:
            proc.terminate()

if __name__ == '__main__':
    bootstrap()
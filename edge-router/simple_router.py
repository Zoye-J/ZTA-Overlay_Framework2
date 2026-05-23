#!/usr/bin/env python
"""Simplified Edge Router for testing - The "Secret Sauce" of ZTA Overlay"""
import os
import sys
import yaml
import json
import requests
from flask import Flask, request, Response

# Add parent to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')
if not os.path.exists(CONFIG_PATH):
    # Create default config if not exists
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    default_config = {
        'identity': {
            'name': 'edge-router-01',
            'type': 'router'
        },
        'controller': {
            'url': 'http://localhost:8080',
            'host': 'localhost',
            'port': 8080,
            'heartbeat_interval': 30
        },
        'local': {
            'proxy_port': 9999,
            'default_service': 'gateway'
        }
    }
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False)

with open(CONFIG_PATH, 'r') as f:
    CONFIG = yaml.safe_load(f)

# Service registry - where to route traffic
SERVICE_REGISTRY = {
    'gateway': 'http://127.0.0.1:5000',
    'api_server': 'http://127.0.0.1:5001',
    'opa_agent': 'http://127.0.0.1:8282',
    'dashboard': 'http://127.0.0.1:5002'
}

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy_all(path):
    """Forward all requests to the appropriate service through the overlay"""
    
    # Determine target service
    target_service = request.headers.get('X-Target-Service')
    if not target_service:
        target_service = CONFIG['local']['default_service']
    
    # Check policy with controller
    try:
        policy_check = requests.post(
            f"{CONFIG['controller']['url']}/api/v1/policies/check",
            json={
                'source': CONFIG['identity']['name'],
                'target': target_service,
                'action': 'dial'
            },
            timeout=2
        )
        
        if policy_check.status_code != 200 or not policy_check.json().get('allowed'):
            return {'error': 'Access denied by policy', 'target': target_service}, 403
    except Exception as e:
        print(f"Policy check failed: {e}, allowing by default for development")
    
    # Get the actual service URL
    service_url = SERVICE_REGISTRY.get(target_service)
    if not service_url:
        return {'error': f'Unknown service: {target_service}'}, 404
    
    # Build the full URL
    full_url = f"{service_url}/{path}"
    
    # Forward the request
    try:
        # Prepare headers (remove the X-Target-Service header)
        headers = {k: v for k, v in request.headers.items() 
                  if k.lower() not in ['x-target-service', 'host']}
        
        # Forward the request
        response = requests.request(
            method=request.method,
            url=full_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30
        )
        
        # Return the response
        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
        
    except requests.exceptions.ConnectionError:
        return {'error': f'Service {target_service} is not available'}, 503
    except Exception as e:
        return {'error': f'Proxy error: {str(e)}'}, 500

@app.route('/health', methods=['GET'])
def health():
    """Health check for the edge router"""
    return {
        'status': 'healthy',
        'identity': CONFIG['identity']['name'],
        'proxy_port': CONFIG['local']['proxy_port'],
        'registered_services': list(SERVICE_REGISTRY.keys())
    }

@app.route('/services', methods=['GET'])
def list_services():
    """List all registered services"""
    return {'services': SERVICE_REGISTRY}

if __name__ == '__main__':
    print("=" * 60)
    print("ZTA Edge Router - The Overlay Network Gateway")
    print("=" * 60)
    print(f"Identity: {CONFIG['identity']['name']}")
    print(f"Listening on: 127.0.0.1:{CONFIG['local']['proxy_port']}")
    print(f"Registered services: {', '.join(SERVICE_REGISTRY.keys())}")
    print("")
    print("This router acts as the overlay network - no inbound ports exposed!")
    print("All traffic is forwarded through this secure proxy")
    print("=" * 60)
    
    app.run(host='127.0.0.1', port=CONFIG['local']['proxy_port'], debug=True, use_reloader=False)
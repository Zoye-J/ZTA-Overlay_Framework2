#!/usr/bin/env python
"""Simplified Edge Router for testing - The "Secret Sauce" of ZTA Overlay"""
import os
import sys
import yaml
import json
import requests
from flask import Flask, request, Response
from flask_cors import CORS

# Add parent to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')
if not os.path.exists(CONFIG_PATH):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    default_config = {
        'identity': {'name': 'edge-router-01', 'type': 'router'},
        'controller': {'url': 'http://localhost:8080', 'host': 'localhost', 'port': 8080, 'heartbeat_interval': 30},
        'local': {'proxy_port': 9999, 'default_service': 'gateway'}
    }
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False)

with open(CONFIG_PATH, 'r') as f:
    CONFIG = yaml.safe_load(f)

# Service registry
SERVICE_REGISTRY = {
    'gateway': 'http://127.0.0.1:5000',
    'api_server': 'http://127.0.0.1:5001',
    'opa_agent': 'http://127.0.0.1:8282',
    'dashboard': 'http://127.0.0.1:5002'
}

app = Flask(__name__)

# Enable CORS properly
CORS(app, origins='*', supports_credentials=True)

@app.after_request
def after_request(response):
    """Add CORS headers to every response"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Target-Service')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS, PATCH')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy_all(path):
    """Forward all requests to the appropriate service"""
    
    # Handle OPTIONS preflight
    if request.method == "OPTIONS":
        return Response(status=200)
    
    # Determine target service
    target_service = request.headers.get('X-Target-Service')
    if not target_service:
        target_service = CONFIG['local']['default_service']
    
    print(f"[Edge Router] Proxying {request.method} /{path} -> {target_service}")
    
    # Get the actual service URL
    service_url = SERVICE_REGISTRY.get(target_service)
    if not service_url:
        return Response(
            response=json.dumps({'error': f'Unknown service: {target_service}'}),
            status=404,
            mimetype='application/json'
        )
    
    # Build the full URL
    if path:
        full_url = f"{service_url}/{path}"
    else:
        full_url = service_url
    
    # Forward the request
    try:
        # Prepare headers (remove problematic ones)
        forward_headers = {}
        for k, v in request.headers.items():
            if k.lower() not in ['x-target-service', 'host', 'content-length', 'origin']:
                forward_headers[k] = v
        
        # Forward the request
        resp = requests.request(
            method=request.method,
            url=full_url,
            headers=forward_headers,
            data=request.get_data(),
            timeout=30
        )
        
        # Return response
        response = Response(
            response=resp.content,
            status=resp.status_code,
            headers=dict(resp.headers)
        )
        return response
        
    except requests.exceptions.ConnectionError:
        print(f"[Edge Router] Connection error to {target_service}")
        return Response(
            response=json.dumps({'error': f'Service {target_service} is not available'}),
            status=503,
            mimetype='application/json'
        )
    except Exception as e:
        print(f"[Edge Router] Proxy error: {e}")
        return Response(
            response=json.dumps({'error': f'Proxy error: {str(e)}'}),
            status=500,
            mimetype='application/json'
        )

@app.route('/health', methods=['GET'])
def health():
    return Response(
        response=json.dumps({
            'status': 'healthy',
            'identity': CONFIG['identity']['name'],
            'services': list(SERVICE_REGISTRY.keys())
        }),
        status=200,
        mimetype='application/json'
    )

if __name__ == '__main__':
    print("=" * 60)
    print("ZTA Edge Router - Overlay Network Gateway")
    print("=" * 60)
    print(f"Listening on: 0.0.0.0:{CONFIG['local']['proxy_port']}")
    print(f"Services: {', '.join(SERVICE_REGISTRY.keys())}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=CONFIG['local']['proxy_port'], debug=True, use_reloader=False)
"""Simplified Edge Router for testing - The "Secret Sauce" of ZTA Overlay"""
import os
import sys
import yaml
import json
import requests
from flask import Flask, request, Response
from flask_cors import CORS
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

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

# Service registry - Uses HTTPS
SERVICE_REGISTRY = {
    'gateway': 'https://127.0.0.1:5000',
    'api_server': 'https://127.0.0.1:5001',
    'opa_agent': 'https://127.0.0.1:8282',
    'dashboard': 'https://127.0.0.1:5002'
}

app = Flask(__name__)

# Simple CORS - allow everything for development
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Target-Service'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy_all(path):
    """Forward all requests to the appropriate service"""
    
    # Handle OPTIONS preflight
    if request.method == "OPTIONS":
        return Response(status=200)
    
    target_service = request.headers.get('X-Target-Service')
    if not target_service:
        target_service = CONFIG['local']['default_service']
    
    print(f"[Edge Router] Proxying {request.method} /{path} -> {target_service}")
    
    service_url = SERVICE_REGISTRY.get(target_service)
    if not service_url:
        return Response(
            response=json.dumps({'error': f'Unknown service: {target_service}'}),
            status=404,
            mimetype='application/json'
        )
    
    full_url = f"{service_url}/{path}" if path else service_url
    
    try:
        forward_headers = {}
        for k, v in request.headers.items():
            if k.lower() not in ['x-target-service', 'host', 'content-length']:
                forward_headers[k] = v
        
        # Forward the request
        resp = requests.request(
            method=request.method,
            url=full_url,
            headers=forward_headers,
            data=request.get_data(),
            timeout=30,
            verify=False
        )
        
        # Create response
        response = Response(resp.content, status=resp.status_code)
        
        # Copy important response headers
        if 'Content-Type' in resp.headers:
            response.headers['Content-Type'] = resp.headers['Content-Type']
        
        return response
        
    except requests.exceptions.ConnectionError as e:
        print(f"[Edge Router] Connection error: {e}")
        return Response(
            response=json.dumps({'error': f'Service {target_service} unavailable'}),
            status=503,
            mimetype='application/json'
        )
    except Exception as e:
        print(f"[Edge Router] Proxy error: {e}")
        return Response(
            response=json.dumps({'error': str(e)}),
            status=500,
            mimetype='application/json'
        )

@app.route('/health', methods=['GET'])
def health():
    return Response(
        response=json.dumps({
            'status': 'healthy',
            'services': list(SERVICE_REGISTRY.keys())
        }),
        status=200,
        mimetype='application/json'
    )

if __name__ == '__main__':
    print("=" * 60)
    print("ZTA Edge Router - HTTPS Proxy")
    print("=" * 60)
    print(f"Listening on: https://0.0.0.0:{CONFIG['local']['proxy_port']}")
    print("=" * 60)
    
    cert_path = os.path.join(BASE_DIR, 'certs', 'identities', 'gateway', 'gateway.crt')
    key_path = os.path.join(BASE_DIR, 'certs', 'identities', 'gateway', 'gateway.key')
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        app.run(host='0.0.0.0', port=CONFIG['local']['proxy_port'], 
                debug=True, use_reloader=False, ssl_context=(cert_path, key_path))
    else:
        print("Certificate not found, using HTTP")
        app.run(host='0.0.0.0', port=CONFIG['local']['proxy_port'], 
                debug=True, use_reloader=False)
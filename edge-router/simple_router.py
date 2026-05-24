"""Simplified Edge Router for testing - The "Secret Sauce" of ZTA Overlay"""
import os
import sys
import yaml
import json
import requests
from flask import Flask, request, Response
from flask_cors import CORS
import urllib3
import ssl

# Disable SSL warnings for self-signed certs
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


@app.after_request
def add_cors_headers(response):
    # Get the origin from the request
    origin = request.headers.get('Origin', '')
    # Allow requests from localhost:5000
    if origin and ('localhost:5000' in origin or '127.0.0.1:5000' in origin):
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = 'https://localhost:5000'
    
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Target-Service'
    # Don't set Allow-Credentials when using specific origin
    return response

# Create a custom session with SSL verification disabled
session = requests.Session()
session.verify = False

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy_all(path):
    """Forward all requests to the appropriate service"""
    
    # Handle OPTIONS preflight
    if request.method == "OPTIONS":
        response = Response(status=200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Target-Service'
        return response
    
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
    
    # Build the full URL
    if path:
        full_url = f"{service_url}/{path}"
    else:
        full_url = service_url
    
    try:
        # Prepare headers
        forward_headers = {}
        for k, v in request.headers.items():
            if k.lower() not in ['x-target-service', 'host', 'content-length']:
                forward_headers[k] = v
        
        # Forward the request using the session with SSL verification disabled
        resp = session.request(
            method=request.method,
            url=full_url,
            headers=forward_headers,
            data=request.get_data(),
            timeout=30
        )
        
        # Create response
        response = Response(resp.content, status=resp.status_code)
        
        # Copy important response headers
        if 'Content-Type' in resp.headers:
            response.headers['Content-Type'] = resp.headers['Content-Type']
        
        # Add CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Target-Service'
        
        return response
        
    except requests.exceptions.ConnectionError as e:
        print(f"[Edge Router] Connection error to {target_service}: {e}")
        return Response(
            response=json.dumps({'error': f'Service {target_service} unavailable', 'details': str(e)}),
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
    
    # Use a simple SSL context that accepts all connections
    if os.path.exists(cert_path) and os.path.exists(key_path):
        # Create SSL context that doesn't verify client certs
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_path, key_path)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        app.run(host='0.0.0.0', port=CONFIG['local']['proxy_port'], 
                debug=True, use_reloader=False, ssl_context=ssl_context)
    else:
        print("Certificate not found, using HTTP")
        app.run(host='0.0.0.0', port=CONFIG['local']['proxy_port'], 
                debug=True, use_reloader=False)
import os
import yaml
from flask import Flask, jsonify, request
import requests

# Load config - NO HARDCODES
with open('config.yaml', 'r') as f:
    SERVICE_CONFIG = yaml.safe_load(f)

app = Flask(__name__)

# IMPORTANT: This service ONLY binds to localhost
# It receives traffic from the local Edge Router, NOT directly from clients
LOCAL_PROXY_PORT = SERVICE_CONFIG['local']['edge_router_proxy_port']
LOCAL_PROXY_HOST = SERVICE_CONFIG['local']['edge_router_proxy_host']  # Always 127.0.0.1

@app.route('/api/v1/login', methods=['POST'])
def login():
    """
    User login - receives request from Edge Router
    """
    data = request.json
    
    # The Edge Router has already verified policies
    # Now we just handle business logic
    
    return jsonify({
        'status': 'success',
        'message': 'Login successful',
        'user': data.get('username')
    })

@app.route('/api/v1/documents', methods=['GET'])
def get_documents():
    """
    Get documents for user
    """
    # To call another service (e.g., API server), we send to local Edge Router
    # The Edge Router will forward through the overlay network
    response = requests.get(
        f"http://{LOCAL_PROXY_HOST}:{LOCAL_PROXY_PORT}/api/documents",
        headers={'X-Target-Service': 'api_server'}
    )
    
    return jsonify(response.json())

if __name__ == '__main__':
    # Bind ONLY to localhost - no public ports!
    app.run(
        host=SERVICE_CONFIG['service']['bind_host'],  # Should be 127.0.0.1
        port=SERVICE_CONFIG['service']['port']
    )
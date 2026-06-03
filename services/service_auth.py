# Create this file at: services/service_auth.py
"""Service-to-service authentication using tokens"""
import os
import secrets
from functools import wraps
from flask import request, jsonify

# Generate secure service tokens (in production, store in environment)
SERVICE_TOKENS = {
    'gateway': os.environ.get('GATEWAY_TOKEN', secrets.token_urlsafe(32)),
    'api_server': os.environ.get('API_TOKEN', secrets.token_urlsafe(32)),
    'edge_router': os.environ.get('EDGE_ROUTER_TOKEN', secrets.token_urlsafe(32)),
    'controller': os.environ.get('CONTROLLER_TOKEN', secrets.token_urlsafe(32)),
}

def require_service_token(f):
    """Decorator to require valid service token for internal API calls"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Service-Token')
        service_name = request.headers.get('X-Service-Name')
        
        if not token:
            return jsonify({'error': 'Service token required'}), 401
        
        # Validate token
        expected_token = SERVICE_TOKENS.get(service_name)
        if not expected_token or token != expected_token:
            return jsonify({'error': 'Invalid service token'}), 401
        
        request.service_name = service_name
        return f(*args, **kwargs)
    return decorated

def get_service_token(service_name):
    """Get token for a service"""
    return SERVICE_TOKENS.get(service_name)
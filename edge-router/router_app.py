import os
import yaml
import socket
import ssl
import threading
import requests
from flask import Flask, request, Response
import json

# Load router config - NO HARDCODES
with open('config.yaml', 'r') as f:
    ROUTER_CONFIG = yaml.safe_load(f)

# Load network config
with open('../config/network_config.yaml', 'r') as f:
    NETWORK_CONFIG = yaml.safe_load(f)

class EdgeRouter:
    """
    The Edge Router - This is the "secret sauce"
    Acts as a local proxy that forwards traffic to the overlay network
    """
    
    def __init__(self):
        self.identity = ROUTER_CONFIG['identity']
        self.local_proxy_port = ROUTER_CONFIG['local']['proxy_port']
        self.controller_url = ROUTER_CONFIG['controller']['url']
        self.mtls_tunnel = None
        
    def start(self):
        """Start the edge router"""
        print(f"Starting Edge Router for identity: {self.identity['name']}")
        
        # Establish mTLS tunnel to controller
        self.establish_mtls_tunnel()
        
        # Start local proxy server
        self.start_local_proxy()
        
        # Start heartbeat thread
        self.start_heartbeat()
        
    def establish_mtls_tunnel(self):
        """Establish outbound mTLS connection to controller - NO open inbound ports"""
        print(f"Establishing outbound mTLS tunnel to {self.controller_url}")
        
        # Load certificates from config
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(
            certfile=self.identity['cert_path'],
            keyfile=self.identity['key_path']
        )
        context.load_verify_locations(cafile=self.identity['ca_cert_path'])
        
        # Create socket - OUTBOUND connection only
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.mtls_tunnel = context.wrap_socket(sock, server_hostname=self.controller_url)
        
        # Connect OUTBOUND - no inbound ports!
        controller_host = ROUTER_CONFIG['controller']['host']
        controller_port = ROUTER_CONFIG['controller']['port']
        self.mtls_tunnel.connect((controller_host, controller_port))
        
        print("mTLS tunnel established successfully")
        
    def start_local_proxy(self):
        """Start local HTTP proxy that accepts traffic from local apps"""
        app = Flask(__name__)
        
        @app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
        @app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
        def proxy_all(path):
            """Forward all requests to the overlay network"""
            
            # Determine target service from the Host header or config
            target_service = request.headers.get('X-Target-Service')
            if not target_service:
                target_service = ROUTER_CONFIG['local']['default_service']
            
            # Check policy with controller
            policy_check = requests.post(
                f"{self.controller_url}/api/v1/policies/check",
                json={
                    'source': self.identity['name'],
                    'target': target_service,
                    'action': 'dial'
                }
            )
            
            if policy_check.status_code != 200 or not policy_check.json().get('allowed'):
                return {'error': 'Access denied by policy'}, 403
            
            # Forward request through mTLS tunnel to the target service's router
            # This is the key - traffic goes OVER the overlay network
            request_data = {
                'method': request.method,
                'path': path,
                'headers': dict(request.headers),
                'body': request.get_data(as_text=True),
                'target_service': target_service
            }
            
            self.mtls_tunnel.send(json.dumps(request_data).encode())
            
            # Wait for response from the overlay
            response_data = self.mtls_tunnel.recv(65536)
            response_json = json.loads(response_data.decode())
            
            return Response(
                response_json.get('body', ''),
                status=response_json.get('status_code', 200),
                headers=response_json.get('headers', {})
            )
        
        # Run local proxy on localhost only - NO public exposure
        app.run(host='127.0.0.1', port=self.local_proxy_port)
        
    def start_heartbeat(self):
        """Send periodic heartbeats to controller"""
        def heartbeat_loop():
            import time
            while True:
                try:
                    heartbeat_data = {
                        'identity': self.identity['name'],
                        'status': 'active',
                        'timestamp': time.time()
                    }
                    self.mtls_tunnel.send(json.dumps(heartbeat_data).encode())
                except Exception as e:
                    print(f"Heartbeat failed: {e}")
                    self.establish_mtls_tunnel()  # Reconnect
                time.sleep(ROUTER_CONFIG['controller']['heartbeat_interval'])
        
        thread = threading.Thread(target=heartbeat_loop, daemon=True)
        thread.start()

if __name__ == '__main__':
    router = EdgeRouter()
    router.start()
"""Shared mTLS configuration for all services"""
import ssl
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CA_CERT_PATH = os.path.join(BASE_DIR, 'certs', 'ca.crt')

def create_mtls_context(service_name):
    """Create mTLS context for a service"""
    cert_path = os.path.join(BASE_DIR, 'certs', 'identities', service_name, f'{service_name}.crt')
    key_path = os.path.join(BASE_DIR, 'certs', 'identities', service_name, f'{service_name}.key')
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"Certificates for {service_name} not found")
    
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(cert_path, key_path)
    context.load_verify_locations(CA_CERT_PATH)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    
    return context

def create_mtls_client_context():
    """Create mTLS context for client connections (service-to-service)"""
    context = ssl.create_default_context()
    context.load_verify_locations(CA_CERT_PATH)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context
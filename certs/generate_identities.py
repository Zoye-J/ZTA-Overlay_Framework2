#!/usr/bin/env python
"""Generate all certificates for the overlay network using pyOpenSSL"""
import os
import sys
from OpenSSL import crypto
import datetime

def generate_ca():
    """Generate Certificate Authority"""
    print("Generating Certificate Authority...")
    
    # Generate key pair
    ca_key = crypto.PKey()
    ca_key.generate_key(crypto.TYPE_RSA, 2048)
    
    # Create certificate
    ca_cert = crypto.X509()
    ca_cert.set_version(2)
    ca_cert.set_serial_number(1)
    
    subject = ca_cert.get_subject()
    subject.C = "BD"
    subject.ST = "Dhaka"
    subject.L = "Dhaka"
    subject.O = "Bangladesh ZTA"
    subject.CN = "ZTA Overlay CA"
    
    ca_cert.set_issuer(subject)
    ca_cert.set_pubkey(ca_key)
    ca_cert.gmtime_adj_notBefore(0)
    ca_cert.gmtime_adj_notAfter(3650 * 24 * 3600)  # 10 years
    ca_cert.add_extensions([
        crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE"),
        crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"),
    ])
    
    ca_cert.sign(ca_key, "sha256")
    
    # Save CA key
    with open("ca.key", "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key))
    
    # Save CA cert
    with open("ca.crt", "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert))
    
    print("CA generated successfully")
    return ca_key, ca_cert

def generate_identity_cert(ca_key, ca_cert, identity_name):
    """Generate certificate for a specific identity"""
    print(f"Generating certificate for {identity_name}...")
    
    # Generate key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    
    # Create certificate
    cert = crypto.X509()
    cert.set_version(2)
    cert.set_serial_number(int(datetime.datetime.now().timestamp()))
    
    subject = cert.get_subject()
    subject.C = "BD"
    subject.O = "Bangladesh ZTA"
    subject.CN = identity_name
    
    cert.set_issuer(ca_cert.get_subject())
    cert.set_pubkey(key)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365 * 24 * 3600)  # 1 year
    
    # Add SAN extension for localhost
    san = crypto.X509Extension(
        b"subjectAltName",
        False,
        b"DNS:localhost,DNS:127.0.0.1,DNS:" + identity_name.encode()
    )
    cert.add_extensions([san])
    
    # Add key usage
    key_usage = crypto.X509Extension(
        b"keyUsage",
        True,
        b"digitalSignature, keyEncipherment"
    )
    cert.add_extensions([key_usage])
    
    cert.sign(ca_key, "sha256")
    
    # Create directory
    os.makedirs(f"identities/{identity_name}", exist_ok=True)
    
    # Save private key
    with open(f"identities/{identity_name}/{identity_name}.key", "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    
    # Save certificate
    with open(f"identities/{identity_name}/{identity_name}.crt", "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    
    print(f"  ✓ Saved to certs/identities/{identity_name}/")
    return cert

def main():
    """Generate all certificates"""
    print("=== Generating Certificates for ZTA Overlay Network ===\n")
    
    # Change to certs directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Generate CA
    ca_key, ca_cert = generate_ca()
    
    # List of services
    services = ['controller', 'gateway', 'api-server', 'opa-agent', 'dashboard']
    
    # Generate certificates for each service
    for service in services:
        generate_identity_cert(ca_key, ca_cert, service)
    
    # Generate client certificate template
    generate_identity_cert(ca_key, ca_cert, 'client-template')
    
    print("\n=== All certificates generated successfully! ===")
    print(f"CA Certificate: {os.path.join(script_dir, 'ca.crt')}")
    print(f"CA Key: {os.path.join(script_dir, 'ca.key')}")
    print("\nIdentity certificates:")
    for service in services:
        print(f"  - {service}: certs/identities/{service}/")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCertificate generation interrupted.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
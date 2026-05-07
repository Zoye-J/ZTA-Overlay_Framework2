#!/usr/bin/env python
"""
Generate all certificates for the overlay network
Compatible with Python 3.13
"""
import os
import sys
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime

def generate_ca():
    """Generate Certificate Authority"""
    print("Generating Certificate Authority...")
    
    # Generate private key (simplified for Python 3.13)
    ca_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,  # Reduced from 4096 for faster generation
    )
    
    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BD"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Dhaka"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Dhaka"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Bangladesh ZTA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "ZTA Overlay CA"),
    ])
    
    # Build certificate
    cert_builder = x509.CertificateBuilder()
    cert_builder = cert_builder.subject_name(subject)
    cert_builder = cert_builder.issuer_name(issuer)
    cert_builder = cert_builder.public_key(ca_key.public_key())
    cert_builder = cert_builder.serial_number(x509.random_serial_number())
    cert_builder = cert_builder.not_valid_before(datetime.datetime.utcnow())
    cert_builder = cert_builder.not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
    cert_builder = cert_builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    )
    
    # Sign the certificate
    ca_cert = cert_builder.sign(ca_key, hashes.SHA256())
    
    # Save CA key
    with open("ca.key", "wb") as f:
        f.write(ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # Save CA cert
    with open("ca.crt", "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    
    print("CA generated successfully")
    return ca_key, ca_cert

def generate_identity_cert(ca_key, ca_cert, identity_name):
    """Generate certificate for a specific identity"""
    print(f"Generating certificate for {identity_name}...")
    
    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Build certificate
    cert_builder = x509.CertificateBuilder()
    cert_builder = cert_builder.subject_name(x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BD"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Bangladesh ZTA"),
        x509.NameAttribute(NameOID.COMMON_NAME, identity_name),
    ]))
    cert_builder = cert_builder.issuer_name(ca_cert.subject)
    cert_builder = cert_builder.public_key(key.public_key())
    cert_builder = cert_builder.serial_number(x509.random_serial_number())
    cert_builder = cert_builder.not_valid_before(datetime.datetime.utcnow())
    cert_builder = cert_builder.not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    cert_builder = cert_builder.add_extension(
        x509.BasicConstraints(ca=False, path_length=None), critical=True
    )
    
    # Sign the certificate
    cert = cert_builder.sign(ca_key, hashes.SHA256())
    
    # Create directory
    os.makedirs(f"identities/{identity_name}", exist_ok=True)
    
    # Save private key
    with open(f"identities/{identity_name}/{identity_name}.key", "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # Save certificate
    with open(f"identities/{identity_name}/{identity_name}.crt", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
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
        print("\n\nCertificate generation interrupted. Run again to complete.")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nIf you see OpenSSL errors, try:")
        print("  pip install --upgrade cryptography")
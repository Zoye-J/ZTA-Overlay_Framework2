#!/usr/bin/env python
"""Setup fresh database with proper encryption"""
import sqlite3
import os
import base64
import json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

DB_PATH = 'database/api.db'
os.makedirs('database', exist_ok=True)

# Generate a master RSA key pair for the system (in production, each user has their own)
# For demo, we'll use a fixed key
SYSTEM_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
SYSTEM_PUBLIC_KEY = SYSTEM_PRIVATE_KEY.public_key()

# Save keys for demo
with open('database/system_public_key.pem', 'wb') as f:
    f.write(SYSTEM_PUBLIC_KEY.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ))

def encrypt_document(content):
    """Encrypt document with AES-256-GCM, then encrypt AES key with RSA"""
    # Generate random AES key for this document
    aes_key = os.urandom(32)
    
    # Encrypt content with AES-GCM
    iv = os.urandom(12)
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(content.encode()) + encryptor.finalize()
    
    # Encrypt AES key with system RSA public key
    encrypted_aes_key = SYSTEM_PUBLIC_KEY.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    return {
        'ciphertext': base64.b64encode(ciphertext).decode(),
        'iv': base64.b64encode(iv).decode(),
        'tag': base64.b64encode(encryptor.tag).decode(),
        'encrypted_key': base64.b64encode(encrypted_aes_key).decode()
    }

# Sample documents
documents = [
    ('Public Service Announcement', 
     'This is a public announcement about government services in Bangladesh. All citizens are encouraged to participate in the Digital Bangladesh initiative.',
     'BASIC', 'General', 1),
    
    ('Confidential Strategy Report', 
     'CONFIDENTIAL: Internal strategy document for Bangladesh Vision 2041 development plan. This document outlines key economic and social development strategies for the next 15 years.',
     'CONFIDENTIAL', 'General', 1),
    
    ('Defense Capability Assessment', 
     'SECRET: Assessment of Bangladesh defense capabilities and border security measures. Includes analysis of current military readiness, equipment modernization, and future strategic requirements.',
     'SECRET', 'Defense', 2),
    
    ('Intelligence Brief - TOP SECRET', 
     'TOP SECRET: Intelligence briefing on national security matters. Access restricted to authorized intelligence personnel during business hours (8 AM - 4 PM) only. Contains sensitive information about regional security dynamics.',
     'TOP_SECRET', 'Intelligence', 1),
    
    ('Foreign Relations Summary', 
     'CONFIDENTIAL: Summary of foreign relations with neighboring countries and recent diplomatic initiatives in South Asia. Includes analysis of bilateral agreements and regional cooperation.',
     'CONFIDENTIAL', 'Foreign', 3),
    
    ('Military Exercise Plan', 
     'SECRET: Planned military exercise "SAMRIDDHI" details and schedule for 2026. Includes troop movements, strategic objectives, and coordination with allied forces.',
     'SECRET', 'Defense', 2),
    
    ('Digital Bangladesh Progress', 
     'BASIC: Progress report on Digital Bangladesh initiative highlighting achievements in e-governance, connectivity, and digital services for citizens.',
     'BASIC', 'General', 1),
]

# Create database
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Create tables with encryption columns
c.execute('''CREATE TABLE IF NOT EXISTS documents
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              content TEXT NOT NULL,
              classification TEXT NOT NULL,
              department TEXT NOT NULL,
              author_id INTEGER NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              encrypted_key TEXT,
              encryption_iv TEXT,
              encryption_tag TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS access_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              document_id INTEGER NOT NULL,
              action TEXT NOT NULL,
              timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# Insert encrypted documents
for title, content, classification, department, author_id in documents:
    encrypted = encrypt_document(content)
    encrypted_content = json.dumps(encrypted)
    
    c.execute('''INSERT INTO documents 
                 (title, content, classification, department, author_id, encrypted_key, encryption_iv, encryption_tag)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (title, encrypted_content, classification, department, author_id, 
               encrypted['encrypted_key'], encrypted['iv'], encrypted['tag']))
    print(f"✓ Added encrypted document: {title}")

conn.commit()

# Verify
c.execute('SELECT id, title, content FROM documents')
print("\nVerification - Documents are encrypted:")
for row in c.fetchall():
    print(f"  Doc {row[0]}: {row[1]} -> {row[2][:50]}...")

conn.close()

print("\n" + "=" * 60)
print("Database created with properly encrypted documents!")
print("Each document is encrypted with AES-256-GCM")
print("AES keys are encrypted with RSA-2048")
print("=" * 60)
# save as reset_encrypted_db.py
import sqlite3
import json
import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

DB_PATH = 'database/api.db'

def generate_document_key():
    return os.urandom(32)

def encrypt_document(content, document_key):
    iv = os.urandom(12)
    cipher = Cipher(algorithms.AES(document_key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(content.encode()) + encryptor.finalize()
    return {
        'ciphertext': base64.b64encode(ciphertext).decode(),
        'iv': base64.b64encode(iv).decode(),
        'tag': base64.b64encode(encryptor.tag).decode()
    }

# Generate a sample document key (in production, this would be per user)
sample_key = generate_document_key()

# Sample documents with proper encryption
documents = [
    ('Public Service Announcement', 
     'This is a public announcement about government services in Bangladesh. All citizens are encouraged to participate in the Digital Bangladesh initiative.',
     'BASIC', 'General', 1),
    
    ('Confidential Strategy Report', 
     'CONFIDENTIAL: Internal strategy document for Bangladesh Vision 2041 development plan. This document outlines key economic and social development strategies.',
     'CONFIDENTIAL', 'General', 1),
    
    ('Defense Capability Assessment', 
     'SECRET: Assessment of Bangladesh defense capabilities and border security measures. Includes analysis of current military readiness and future requirements.',
     'SECRET', 'Defense', 2),
    
    ('Intelligence Brief - TOP SECRET', 
     'TOP SECRET: Intelligence briefing on national security matters. Access restricted to authorized intelligence personnel during business hours (8 AM - 4 PM) only.',
     'TOP_SECRET', 'Intelligence', 1),
    
    ('Foreign Relations Summary', 
     'CONFIDENTIAL: Summary of foreign relations with neighboring countries and recent diplomatic initiatives in South Asia.',
     'CONFIDENTIAL', 'Foreign', 3),
    
    ('Military Exercise Plan', 
     'SECRET: Planned military exercise "SAMRIDDHI" details and schedule for 2026. Includes troop movements and strategic objectives.',
     'SECRET', 'Defense', 2),
    
    ('Digital Bangladesh Progress', 
     'BASIC: Progress report on Digital Bangladesh initiative highlighting achievements in e-governance, connectivity, and digital services.',
     'BASIC', 'General', 1),
]

# Connect and reset database
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Drop and recreate tables
c.execute('DROP TABLE IF EXISTS documents')
c.execute('DROP TABLE IF EXISTS access_logs')

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
    encrypted = encrypt_document(content, sample_key)
    encrypted_content = json.dumps(encrypted)
    
    c.execute('''INSERT INTO documents (title, content, classification, department, author_id, encrypted_key, encryption_iv, encryption_tag)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (title, encrypted_content, classification, department, author_id, 
               base64.b64encode(sample_key).decode(), encrypted['iv'], encrypted['tag']))

conn.commit()
conn.close()

print("Database reset with properly encrypted documents!")
print(f"Created {len(documents)} encrypted documents")

# Verify
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('SELECT id, title, classification, content FROM documents')
for row in c.fetchall():
    print(f"  Document {row[0]}: {row[1]} ({row[2]}) - Content type: {type(row[3])}")
conn.close()
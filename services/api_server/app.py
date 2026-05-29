#!/usr/bin/env python
"""Zitified API Server - Handles business logic and database operations"""
import os
import sys
import yaml
import sqlite3
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify
import jwt
import secrets
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import base64
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(CONFIG_PATH, 'r') as f:
    SERVICE_CONFIG = yaml.safe_load(f)

# Load clearance levels
CLEARANCE_PATH = os.path.join(BASE_DIR, 'config', 'policies', 'clearance_levels.yaml')
with open(CLEARANCE_PATH, 'r') as f:
    CLEARANCE_LEVELS = yaml.safe_load(f)

# Create hierarchy map
CLEARANCE_HIERARCHY = {c['name']: c['level'] for c in CLEARANCE_LEVELS['clearance_hierarchy']}

app = Flask(__name__)
# Use the same SECRET_KEY as gateway - load from env
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Database
DB_PATH = os.path.join(BASE_DIR, 'database', 'api.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


class DocumentEncryption:
    """Handle document encryption/decryption for Framework 2"""
    
    @staticmethod
    def generate_document_key():
        """Generate a random AES key for document encryption"""
        return os.urandom(32)  # 256-bit AES key
    
    @staticmethod
    def encrypt_document(content, document_key):
        """Encrypt document content with AES-GCM"""
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(document_key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(content.encode()) + encryptor.finalize()
        
        return {
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'iv': base64.b64encode(iv).decode(),
            'tag': base64.b64encode(encryptor.tag).decode()
        }
    
    @staticmethod
    def decrypt_document(encrypted_data, document_key):
        """Decrypt document content"""
        ciphertext = base64.b64decode(encrypted_data['ciphertext'])
        iv = base64.b64decode(encrypted_data['iv'])
        tag = base64.b64decode(encrypted_data['tag'])
        
        cipher = Cipher(algorithms.AES(document_key), modes.GCM(iv, tag))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        
        return decrypted.decode()
    
    @staticmethod
    def encrypt_document_key_for_user(document_key, user_public_key_pem):
        """Encrypt document key with user's RSA public key"""
        user_public_key = serialization.load_pem_public_key(user_public_key_pem.encode())
        
        encrypted_key = user_public_key.encrypt(
            document_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(encrypted_key).decode()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  classification TEXT NOT NULL,
                  department TEXT NOT NULL,
                  author_id INTEGER NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS access_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  document_id INTEGER NOT NULL,
                  action TEXT NOT NULL,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("[API Server] Database initialized")

init_db()

def verify_token(token):
    """Verify JWT token"""
    if not token:
        return None
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        # Decode token
        payload = jwt.decode(
            token, 
            app.config['SECRET_KEY'], 
            algorithms=['HS256'],
            options={'verify_exp': True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        print("[API Server] Token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"[API Server] Invalid token: {e}")
        return None

def token_required(f):
    """Decorator to verify JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '')
        user = verify_token(token)
        
        if not user:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        request.user = user
        return f(*args, **kwargs)
    return decorated

@app.route('/api/v1/auth/me', methods=['GET'])
@token_required
def get_current_user():
    """Get current user info from token"""
    return jsonify({
        'user_id': request.user.get('user_id'),
        'username': request.user.get('username'),
        'full_name': request.user.get('full_name'),
        'department': request.user.get('department'),
        'clearance_level': request.user.get('clearance_level')
    })

@app.route('/api/v1/auth/verify', methods=['GET'])
@token_required
def verify_token_endpoint():
    """Verify if current token is valid"""
    return jsonify({
        'valid': True,
        'user': request.user,
        'expires_at': request.user.get('exp')
    })

@app.route('/api/v1/documents', methods=['GET'])
@token_required
def get_documents():
    """Get documents accessible to user - Department-based access control"""
    user = request.user
    user_clearance = user.get('clearance_level', 'BASIC')
    user_dept = user.get('department', 'General')
    
    print(f"[API Server] User {user.get('username')} (Clearance: {user_clearance}, Dept: {user_dept}) requesting documents")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT id, title, classification, department, created_at 
                 FROM documents''')
    all_docs = c.fetchall()
    conn.close()
    
    # Filter based on clearance AND department
    docs = []
    for doc in all_docs:
        doc_id, title, doc_clearance, doc_dept, created_at = doc
        
        # Check if user has sufficient clearance
        if CLEARANCE_HIERARCHY.get(user_clearance, 0) < CLEARANCE_HIERARCHY.get(doc_clearance, 0):
            print(f"  [DENIED] {title}: Insufficient clearance (need {doc_clearance}, have {user_clearance})")
            continue
    
        
        if doc_dept == 'General':
            # General documents: visible to everyone
            docs.append({
                'id': doc_id,
                'title': title,
                'classification': doc_clearance,
                'department': doc_dept,
                'created_at': created_at
            })
            print(f"  [ALLOWED] {title}: General document - visible to all departments")
        elif doc_dept == user_dept:
            # Same department: visible
            docs.append({
                'id': doc_id,
                'title': title,
                'classification': doc_clearance,
                'department': doc_dept,
                'created_at': created_at
            })
            print(f"  [ALLOWED] {title}: Same department ({doc_dept})")
        else:
            # Different department: NOT visible
            print(f"  [DENIED] {title}: Different department (doc: {doc_dept}, user: {user_dept})")
            continue
    
    print(f"[API Server] Returning {len(docs)} documents for {user_dept} department user")
    return jsonify({'documents': docs})

@app.route('/api/v1/documents/<int:doc_id>', methods=['GET'])
@token_required
def get_document(doc_id):
    """Get specific document - Department-based access control"""
    user = request.user
    user_clearance = user.get('clearance_level', 'BASIC')
    user_dept = user.get('department', 'General')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, title, content, classification, department, created_at, encrypted_key 
                 FROM documents WHERE id = ?''', (doc_id,))
    doc = c.fetchone()
    conn.close()
    
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    doc_id, title, content, doc_clearance, doc_dept, created_at, encrypted_key = doc
    
    # Check clearance
    if CLEARANCE_HIERARCHY.get(user_clearance, 0) < CLEARANCE_HIERARCHY.get(doc_clearance, 0):
        return jsonify({'error': f'Insufficient clearance. Required: {doc_clearance}'}), 403
    
    # Department access rules:
    # 1. General department documents: visible to ALL departments
    # 2. Other departments: ONLY visible to users from that department
    if doc_dept != 'General' and doc_dept != user_dept:
        return jsonify({'error': f'Access denied. This document is restricted to {doc_dept} department only.'}), 403
    
    # For TOP_SECRET, additional business hours check
    if doc_clearance == 'TOP_SECRET':
        current_hour = datetime.now().hour
        business_start = int(os.environ.get('BUSINESS_HOURS_START', 8))
        business_end = int(os.environ.get('BUSINESS_HOURS_END', 16))
        if current_hour < business_start or current_hour >= business_end:
            return jsonify({'error': 'TOP_SECRET documents only accessible during business hours (8 AM - 4 PM)'}), 403
    
    # Log access
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO access_logs (user_id, document_id, action) VALUES (?, ?, ?)',
              (user.get('user_id'), doc_id, 'read'))
    conn.commit()
    conn.close()
    
    # Return encrypted document
    return jsonify({
        'id': doc_id,
        'title': title,
        'content': content,
        'classification': doc_clearance,
        'department': doc_dept,
        'created_at': created_at,
        'encrypted': True,
        'encrypted_key': encrypted_key
    })

@app.route('/api/v1/documents', methods=['POST'])
@token_required
def create_document():
    """Create a new document with end-to-end encryption"""
    user = request.user
    data = request.json
    
    # Check clearance
    required_clearance = data.get('classification', 'BASIC')
    user_clearance = user.get('clearance_level', 'BASIC')
    
    if CLEARANCE_HIERARCHY.get(user_clearance, 0) < CLEARANCE_HIERARCHY.get(required_clearance, 0):
        return jsonify({'error': f'Insufficient clearance'}), 403
    
    # Generate document encryption key
    doc_key = DocumentEncryption.generate_document_key()
    
    # Encrypt document content
    encrypted = DocumentEncryption.encrypt_document(data.get('content', ''), doc_key)
    
    # Encrypt document key with user's public key (store for this user)
    # In production, encrypt for multiple authorized users
    encrypted_key_for_user = DocumentEncryption.encrypt_document_key_for_user(
        doc_key, 
        data.get('user_public_key')  # Frontend should send user's public key
    )
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO documents (title, content, classification, department, author_id, encrypted_key, encryption_iv, encryption_tag)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (data.get('title'), 
               json.dumps(encrypted),  # Store encrypted content as JSON
               required_clearance,
               user.get('department'), 
               user.get('user_id'),
               encrypted_key_for_user,
               encrypted['iv'],
               encrypted['tag']))
    conn.commit()
    doc_id = c.lastrowid
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Document created encrypted', 'document_id': doc_id})

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'healthy', 'service': 'api_server'})

if __name__ == '__main__':
    host = SERVICE_CONFIG['service']['bind_host']
    port = SERVICE_CONFIG['service']['port']
    
    # SSL context for HTTPS
    ssl_context = None
    cert_path = os.path.join(BASE_DIR, 'certs', 'identities', 'api-server', 'api-server.crt')
    key_path = os.path.join(BASE_DIR, 'certs', 'identities', 'api-server', 'api-server.key')
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        ssl_context = (cert_path, key_path)
        print(f"API Server starting on https://{host}:{port}")
        app.run(host=host, port=port, debug=True, use_reloader=False, ssl_context=ssl_context)
    else:
        print(f"API Server starting on http://{host}:{port}")
        app.run(host=host, port=port, debug=True, use_reloader=False)
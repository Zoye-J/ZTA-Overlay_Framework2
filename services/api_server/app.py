#!/usr/bin/env python
"""Zitified API Server - Handles business logic and database operations"""
import os
import sys
import yaml
import sqlite3
import json
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify
import jwt

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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me')

# Database
DB_PATH = os.path.join(BASE_DIR, 'database', 'api.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

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

init_db()

def verify_token(token):
    """Verify JWT token"""
    try:
        return jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    except:
        return None

def clearance_required(required_level):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            user = verify_token(token)
            if not user:
                return jsonify({'error': 'Invalid token'}), 401
            
            user_clearance = user.get('clearance_level', 'BASIC')
            if CLEARANCE_HIERARCHY.get(user_clearance, 0) < CLEARANCE_HIERARCHY.get(required_level, 0):
                return jsonify({'error': f'Insufficient clearance. Required: {required_level}'}), 403
            
            request.user = user
            return f(*args, **kwargs)
        return decorated
    return decorator

@app.route('/api/v1/documents', methods=['GET'])
@clearance_required('BASIC')
def get_documents():
    """Get documents accessible to user"""
    user = request.user
    user_clearance = user.get('clearance_level', 'BASIC')
    user_dept = user.get('department', 'General')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get documents based on clearance and department
    c.execute('''SELECT id, title, classification, department, created_at 
                 FROM documents 
                 WHERE 1=1''')
    all_docs = c.fetchall()
    conn.close()
    
    # Filter by clearance hierarchy
    docs = []
    for doc in all_docs:
        doc_clearance = doc[2]
        doc_dept = doc[3]
        
        # Check clearance
        if CLEARANCE_HIERARCHY.get(user_clearance, 0) >= CLEARANCE_HIERARCHY.get(doc_clearance, 0):
            # For TOP_SECRET, check department match
            if doc_clearance == 'TOP_SECRET' and user_dept != doc_dept:
                continue
            docs.append({
                'id': doc[0],
                'title': doc[1],
                'classification': doc[2],
                'department': doc[3],
                'created_at': doc[4]
            })
    
    return jsonify({'documents': docs})

@app.route('/api/v1/documents/<int:doc_id>', methods=['GET'])
@clearance_required('BASIC')
def get_document(doc_id):
    """Get specific document"""
    user = request.user
    user_clearance = user.get('clearance_level', 'BASIC')
    user_dept = user.get('department', 'General')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, title, content, classification, department, created_at FROM documents WHERE id = ?', (doc_id,))
    doc = c.fetchone()
    conn.close()
    
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    # Check access
    if CLEARANCE_HIERARCHY.get(user_clearance, 0) < CLEARANCE_HIERARCHY.get(doc[3], 0):
        return jsonify({'error': 'Insufficient clearance'}), 403
    
    if doc[3] == 'TOP_SECRET' and user_dept != doc[4]:
        return jsonify({'error': 'Department mismatch for TOP_SECRET document'}), 403
    
    # Check business hours for TOP_SECRET
    if doc[3] == 'TOP_SECRET':
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
    
    return jsonify({
        'id': doc[0],
        'title': doc[1],
        'content': doc[2],
        'classification': doc[3],
        'department': doc[4],
        'created_at': doc[5]
    })

@app.route('/api/v1/documents', methods=['POST'])
@clearance_required('CONFIDENTIAL')
def create_document():
    """Create a new document"""
    user = request.user
    data = request.json
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO documents (title, content, classification, department, author_id)
                 VALUES (?, ?, ?, ?, ?)''',
              (data.get('title'), data.get('content'), data.get('classification', 'BASIC'),
               user.get('department'), user.get('user_id')))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Document created'})

if __name__ == '__main__':
    host = SERVICE_CONFIG['service']['bind_host']
    port = SERVICE_CONFIG['service']['port']
    print(f"API Server starting on {host}:{port} (localhost only)")
    app.run(host=host, port=port, debug=True, use_reloader=False)
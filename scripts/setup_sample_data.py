#!/usr/bin/env python
"""Setup sample data for the ZTA overlay network"""
import os
import sys
import sqlite3
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def setup_users():
    """Create sample users for testing"""
    db_path = os.path.join(BASE_DIR, 'database', 'gateway.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  full_name TEXT NOT NULL,
                  department TEXT NOT NULL,
                  clearance_level TEXT NOT NULL,
                  mfa_secret TEXT,
                  is_active BOOLEAN DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  jwt_token TEXT NOT NULL,
                  refresh_token TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  expires_at TIMESTAMP NOT NULL,
                  last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS token_blacklist
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  token TEXT NOT NULL,
                  blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Clear existing users (but keep table)
    c.execute('DELETE FROM users')
    
    # Sample users with Bangladesh government context
    users = [
        ('intelligence_officer', 'password123', 'Kazi Rafiq', 'Intelligence', 'TOP_SECRET'),
        ('defense_staff', 'password123', 'General AKM Shafi', 'Defense', 'SECRET'),
        ('foreign_affairs', 'password123', 'Ambassador Farida Begum', 'Foreign', 'CONFIDENTIAL'),
        ('general_user', 'password123', 'Mohammad Ali', 'General', 'BASIC'),
    ]
    
    for user in users:
        password_hash = hashlib.sha256(user[1].encode()).hexdigest()
        try:
            c.execute('''INSERT INTO users (username, password_hash, full_name, department, clearance_level, is_active)
                         VALUES (?, ?, ?, ?, ?, 1)''', (user[0], password_hash, user[2], user[3], user[4]))
        except sqlite3.IntegrityError:
            pass  # User already exists
    
    conn.commit()
    conn.close()
    print("✓ Users created successfully")

def setup_documents():
    """Create sample documents with different classifications"""
    db_path = os.path.join(BASE_DIR, 'database', 'api.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create tables
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
    
    # Clear existing documents
    c.execute('DELETE FROM documents')
    
    documents = [
        ('Public Service Announcement', 'This is a public announcement about government services in Bangladesh. All citizens are encouraged to participate.', 'BASIC', 'General', 1),
        ('Confidential Strategy Report', 'CONFIDENTIAL: Internal strategy document for Bangladesh Vision 2041 development plan.', 'CONFIDENTIAL', 'General', 1),
        ('Defense Capability Assessment', 'SECRET: Assessment of Bangladesh defense capabilities and border security measures.', 'SECRET', 'Defense', 2),
        ('Intelligence Brief - TOP SECRET', 'TOP SECRET: Intelligence briefing on national security matters. Access restricted to authorized intelligence personnel during business hours (8 AM - 4 PM) only.', 'TOP_SECRET', 'Intelligence', 1),
        ('Foreign Relations Summary', 'CONFIDENTIAL: Summary of foreign relations with neighboring countries and diplomatic initiatives.', 'CONFIDENTIAL', 'Foreign', 3),
        ('Military Exercise Plan', 'SECRET: Planned military exercise "SAMRIDDHI" details and schedule for 2026.', 'SECRET', 'Defense', 2),
        ('Digital Bangladesh Progress', 'BASIC: Progress report on Digital Bangladesh initiative and upcoming projects.', 'BASIC', 'General', 1),
        ('Cyber Security Directive', 'SECRET: Confidential cyber security directives for government agencies.', 'SECRET', 'Intelligence', 1),
    ]
    
    for doc in documents:
        c.execute('''INSERT INTO documents (title, content, classification, department, author_id)
                     VALUES (?, ?, ?, ?, ?)''', doc)
    
    conn.commit()
    conn.close()
    print("✓ Documents created successfully")

def setup_controller_db():
    """Initialize controller database"""
    db_path = os.path.join(BASE_DIR, 'database', 'overlay_network.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create controller tables
    c.execute('''CREATE TABLE IF NOT EXISTS identities
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  identity_type TEXT NOT NULL,
                  certificate_serial TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_seen TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS service_policies
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  identity_id INTEGER,
                  target_service TEXT,
                  action TEXT,
                  is_active BOOLEAN DEFAULT 1,
                  conditions TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS active_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  identity_id INTEGER,
                  session_token TEXT,
                  connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  client_ip TEXT)''')
    
    conn.commit()
    conn.close()
    print("✓ Controller database initialized")

if __name__ == '__main__':
    print("Setting up sample data for ZTA Overlay Network...")
    setup_controller_db()
    setup_users()
    setup_documents()
    print("\n✅ Sample data created successfully!")
    print("\n📋 Test credentials:")
    print("   🕵️ Intelligence Officer: intelligence_officer / password123 (TOP_SECRET)")
    print("   🛡️ Defense Staff: defense_staff / password123 (SECRET)")
    print("   🌍 Foreign Affairs: foreign_affairs / password123 (CONFIDENTIAL)")
    print("   👤 General User: general_user / password123 (BASIC)")
    print("\n📄 Sample documents created with various classifications")
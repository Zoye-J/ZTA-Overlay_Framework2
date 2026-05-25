import sqlite3
import hashlib
import os

DB_PATH = 'database/gateway.db'
os.makedirs('database', exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              full_name TEXT NOT NULL,
              department TEXT NOT NULL,
              clearance_level TEXT NOT NULL,
              is_active BOOLEAN DEFAULT 1,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS user_sessions
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              jwt_token TEXT NOT NULL,
              refresh_token TEXT,
              expires_at TIMESTAMP NOT NULL)''')

c.execute('''CREATE TABLE IF NOT EXISTS token_blacklist
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              token TEXT NOT NULL)''')

# Clear existing
c.execute('DELETE FROM users')

# Create users
users = [
    ('intelligence_officer', 'password123', 'Kazi Rafiq', 'Intelligence', 'TOP_SECRET'),
    ('defense_staff', 'password123', 'General AKM Shafi', 'Defense', 'SECRET'),
    ('foreign_affairs', 'password123', 'Ambassador Farida Begum', 'Foreign', 'CONFIDENTIAL'),
    ('general_user', 'password123', 'Mohammad Ali', 'General', 'BASIC'),
]

for username, password, full_name, department, clearance in users:
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute('''INSERT INTO users (username, password_hash, full_name, department, clearance_level)
                 VALUES (?, ?, ?, ?, ?)''', (username, password_hash, full_name, department, clearance))
    print(f"✓ Created user: {username} ({clearance})")

conn.commit()
conn.close()
print("\nGateway database initialized with users!")
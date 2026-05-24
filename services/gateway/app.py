#services/gateway/app.py
"""Zitified Gateway Service - Only binds to localhost, receives traffic via Edge Router"""
import os
import sys
import yaml
import jwt
import hashlib
import sqlite3
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS

# Add parent to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

# Load config - NO HARDCODES
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(CONFIG_PATH, 'r') as f:
    SERVICE_CONFIG = yaml.safe_load(f)

# Load clearance levels
CLEARANCE_PATH = os.path.join(BASE_DIR, 'config', 'policies', 'clearance_levels.yaml')
with open(CLEARANCE_PATH, 'r') as f:
    CLEARANCE_LEVELS = yaml.safe_load(f)

# Load departments
DEPT_PATH = os.path.join(BASE_DIR, 'config', 'policies', 'departments.yaml')
with open(DEPT_PATH, 'r') as f:
    DEPARTMENTS = yaml.safe_load(f)

app = Flask(__name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Enable CORS for the overlay network
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# JWT Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['JWT_EXPIRY_HOURS'] = SERVICE_CONFIG.get('jwt', {}).get('expiry_hours', 8)
app.config['JWT_ALGORITHM'] = SERVICE_CONFIG.get('jwt', {}).get('algorithm', 'HS256')
app.config['JWT_REFRESH_EXPIRY_DAYS'] = SERVICE_CONFIG.get('jwt', {}).get('refresh_expiry_days', 7)

# Database setup
DB_PATH = os.path.join(BASE_DIR, 'database', 'gateway.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_db():
    """Initialize database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users table
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
    
    # User sessions table for JWT tracking
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  jwt_token TEXT NOT NULL,
                  refresh_token TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  expires_at TIMESTAMP NOT NULL,
                  last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Blacklisted tokens table (for logout)
    c.execute('''CREATE TABLE IF NOT EXISTS token_blacklist
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  token TEXT NOT NULL,
                  blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

def generate_tokens(user_id, username, full_name, department, clearance_level):
    """Generate access and refresh JWT tokens"""
    # Access token (short-lived)
    access_expiry = datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRY_HOURS'])
    access_token = jwt.encode({
        'user_id': user_id,
        'username': username,
        'full_name': full_name,
        'department': department,
        'clearance_level': clearance_level,
        'type': 'access',
        'exp': access_expiry,
        'iat': datetime.utcnow()
    }, app.config['SECRET_KEY'], algorithm=app.config['JWT_ALGORITHM'])
    
    # Refresh token (longer-lived)
    refresh_expiry = datetime.utcnow() + timedelta(days=app.config['JWT_REFRESH_EXPIRY_DAYS'])
    refresh_token = jwt.encode({
        'user_id': user_id,
        'username': username,
        'type': 'refresh',
        'exp': refresh_expiry,
        'iat': datetime.utcnow()
    }, app.config['SECRET_KEY'], algorithm=app.config['JWT_ALGORITHM'])
    
    return access_token, refresh_token, access_expiry

def token_required(f):
    """Decorator to verify JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        try:
            # Check if token is blacklisted
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT id FROM token_blacklist WHERE token = ?', (token,))
            if c.fetchone():
                conn.close()
                return jsonify({'error': 'Token has been revoked'}), 401
            conn.close()
            
            # Decode and verify token
            data = jwt.decode(
                token, 
                app.config['SECRET_KEY'], 
                algorithms=[app.config['JWT_ALGORITHM']]
            )
            
            # Verify it's an access token
            if data.get('type') != 'access':
                return jsonify({'error': 'Invalid token type'}), 401
            
            request.user = data
            
            # Update last activity
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''UPDATE user_sessions 
                         SET last_activity = CURRENT_TIMESTAMP 
                         WHERE jwt_token = ?''', (token,))
            conn.commit()
            conn.close()
            
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({'error': f'Invalid token: {str(e)}'}), 401
        
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('overlay_dashboard.html')

@app.route('/login')
def login_page():
    """Serve login page"""
    return render_template('overlay_login.html')

@app.route('/health', methods=['GET'])
def gateway_health():
    """Health check for gateway service"""
    return jsonify({
        'status': 'healthy',
        'service': 'gateway',
        'port': 5000,
        'protocol': 'https'
    })

@app.route('/api/v1/auth/health', methods=['GET'])
def auth_health():
    """Health check for auth service"""
    return jsonify({'status': 'healthy', 'service': 'gateway'})

@app.route('/dashboard')
def dashboard_page():
    """Serve user dashboard page"""
    # Check for token in query parameter or header
    token = request.args.get('token')
    if token:
        # Store token in session or pass to template
        return render_template('overlay_user_dashboard.html', user=request.user if hasattr(request, 'user') else None, token=token)
    
    # Try to get from header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return render_template('overlay_user_dashboard.html', user=request.user if hasattr(request, 'user') else None, token=token)
    
    # No token found
    return render_template('overlay_user_dashboard.html', user=None, token=None)

@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    """Authenticate user and issue JWT tokens"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, username, password_hash, full_name, department, clearance_level 
                 FROM users WHERE username = ? AND is_active = 1''', (username,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Verify password (using SHA256 - upgrade to bcrypt in production)
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if password_hash != user[2]:
        conn.close()
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Generate JWT tokens
    access_token, refresh_token, expiry = generate_tokens(
        user_id=user[0],
        username=user[1],
        full_name=user[3],
        department=user[4],
        clearance_level=user[5]
    )
    
    # Store session in database
    c.execute('''INSERT INTO user_sessions (user_id, jwt_token, refresh_token, expires_at)
                 VALUES (?, ?, ?, ?)''', (user[0], access_token, refresh_token, expiry))
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'expires_in': app.config['JWT_EXPIRY_HOURS'] * 3600,  # in seconds
        'user': {
            'id': user[0],
            'username': user[1],
            'full_name': user[3],
            'department': user[4],
            'clearance_level': user[5]
        }
    })

@app.route('/api/v1/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh an expired access token using refresh token"""
    data = request.json
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({'error': 'Refresh token is missing'}), 401
    
    try:
        # Decode refresh token
        data = jwt.decode(
            refresh_token,
            app.config['SECRET_KEY'],
            algorithms=[app.config['JWT_ALGORITHM']]
        )
        
        if data.get('type') != 'refresh':
            return jsonify({'error': 'Invalid token type'}), 401
        
        # Get user info from database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT id, username, full_name, department, clearance_level 
                     FROM users WHERE id = ? AND is_active = 1''', (data['user_id'],))
        user = c.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'error': 'User not found'}), 401
        
        # Generate new access token
        new_access_token, _, new_expiry = generate_tokens(
            user_id=user[0],
            username=user[1],
            full_name=user[2],
            department=user[3],
            clearance_level=user[4]
        )
        
        # Update session in database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''UPDATE user_sessions 
                     SET jwt_token = ?, expires_at = ?, last_activity = CURRENT_TIMESTAMP
                     WHERE refresh_token = ?''', (new_access_token, new_expiry, refresh_token))
        conn.commit()
        conn.close()
        
        return jsonify({
            'access_token': new_access_token,
            'token_type': 'Bearer',
            'expires_in': app.config['JWT_EXPIRY_HOURS'] * 3600
        })
        
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Refresh token has expired, please login again'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid refresh token'}), 401

@app.route('/api/v1/auth/logout', methods=['POST'])
@token_required
def logout():
    """Logout user - blacklist the token"""
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        token = token[7:]
    
    # Add token to blacklist
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO token_blacklist (token) VALUES (?)', (token,))
    
    # Remove session
    c.execute('DELETE FROM user_sessions WHERE jwt_token = ?', (token,))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Logged out successfully'})

@app.route('/api/v1/auth/me', methods=['GET'])
@token_required
def get_current_user():
    """Get current user information from token"""
    return jsonify(request.user)

@app.route('/api/v1/auth/verify', methods=['GET'])
@token_required
def verify_token():
    """Verify if current token is valid"""
    return jsonify({
        'valid': True,
        'user': request.user,
        'expires_at': request.user.get('exp')
    })

# Admin endpoints for user management
@app.route('/api/v1/admin/users', methods=['GET'])
@token_required
def list_users():
    """List all users (admin only - requires TOP_SECRET clearance)"""
    if request.user.get('clearance_level') != 'TOP_SECRET':
        return jsonify({'error': 'Admin access required'}), 403
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, username, full_name, department, clearance_level, is_active, created_at FROM users')
    users = c.fetchall()
    conn.close()
    
    return jsonify({
        'users': [
            {
                'id': u[0],
                'username': u[1],
                'full_name': u[2],
                'department': u[3],
                'clearance_level': u[4],
                'is_active': bool(u[5]),
                'created_at': u[6]
            } for u in users
        ]
    })

@app.route('/api/v1/admin/users', methods=['POST'])
@token_required
def create_user():
    """Create a new user (admin only)"""
    if request.user.get('clearance_level') != 'TOP_SECRET':
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.json
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')
    department = data.get('department')
    clearance_level = data.get('clearance_level', 'BASIC')
    
    # Validate clearance level
    valid_levels = [c['name'] for c in CLEARANCE_LEVELS['clearance_hierarchy']]
    if clearance_level not in valid_levels:
        return jsonify({'error': f'Invalid clearance level. Must be one of: {valid_levels}'}), 400
    
    # Validate department
    valid_depts = [d['id'] for d in DEPARTMENTS['bangladesh_government_departments']]
    if department not in valid_depts:
        return jsonify({'error': f'Invalid department. Must be one of: {valid_depts}'}), 400
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO users (username, password_hash, full_name, department, clearance_level)
                     VALUES (?, ?, ?, ?, ?)''', 
                  (username, password_hash, full_name, department, clearance_level))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        
        return jsonify({
            'status': 'success',
            'user_id': user_id,
            'message': 'User created successfully'
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400

if __name__ == '__main__':
    # IMPORTANT: Bind ONLY to localhost - no public ports!
    host = SERVICE_CONFIG['service']['bind_host']
    port = SERVICE_CONFIG['service']['port']
    
    # SSL context for HTTPS
    ssl_context = None
    cert_path = os.path.join(BASE_DIR, 'certs', 'identities', 'gateway', 'gateway.crt')
    key_path = os.path.join(BASE_DIR, 'certs', 'identities', 'gateway', 'gateway.key')
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        ssl_context = (cert_path, key_path)
        print(f"=" * 60)
        print(f"Gateway Service (Zitified) - HTTPS Enabled")
        print(f"=" * 60)
        print(f"  • Binding to: https://{host}:{port}")
        print(f"  • Certificate: {cert_path}")
        print(f"  • Traffic received via: Edge Router on port 9999")
        print(f"  • JWT Algorithm: {app.config['JWT_ALGORITHM']}")
        print(f"  • Token expiry: {app.config['JWT_EXPIRY_HOURS']} hours")
        print(f"=" * 60)
        app.run(host=host, port=port, debug=True, use_reloader=False, ssl_context=ssl_context)
    else:
        print(f"=" * 60)
        print(f"Gateway Service (Zitified) - HTTP Mode (No SSL certs found)")
        print(f"=" * 60)
        print(f"  • Binding to: http://{host}:{port}")
        print(f"=" * 60)
        app.run(host=host, port=port, debug=True, use_reloader=False)
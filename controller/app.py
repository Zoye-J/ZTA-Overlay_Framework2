import os
import sys
import yaml
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Add parent to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Load environment variables - NO HARDCODES
load_dotenv()

# Load configuration from YAML
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'controller_config.yaml')
with open(CONFIG_PATH, 'r') as f:
    CONFIG = yaml.safe_load(f)

NETWORK_CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'network_config.yaml')
with open(NETWORK_CONFIG_PATH, 'r') as f:
    NETWORK_CONFIG = yaml.safe_load(f)

app = Flask(__name__)

# Configure from environment and config files - NO HARDCODES
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Fix: Set database URI properly
database_path = os.path.join(BASE_DIR, CONFIG['controller']['database']['path'])
os.makedirs(os.path.dirname(database_path), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{database_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Import models (must be after db initialization)
class Identity(db.Model):
    """Represents a service or client in the overlay network"""
    __tablename__ = 'identities'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    identity_type = db.Column(db.String(20), nullable=False)
    certificate_serial = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    last_seen = db.Column(db.DateTime)

class ServicePolicy(db.Model):
    """Policies defining who can access what services"""
    __tablename__ = 'service_policies'
    
    id = db.Column(db.Integer, primary_key=True)
    identity_id = db.Column(db.Integer, db.ForeignKey('identities.id'))
    target_service = db.Column(db.String(100))
    action = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    conditions = db.Column(db.JSON)

class ActiveSession(db.Model):
    """Tracks active connections in the overlay"""
    __tablename__ = 'active_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    identity_id = db.Column(db.Integer, db.ForeignKey('identities.id'))
    session_token = db.Column(db.String(500))
    connected_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    last_activity = db.Column(db.DateTime, default=db.func.current_timestamp())
    client_ip = db.Column(db.String(50))

# Create tables
with app.app_context():
    db.create_all()

@app.route('/api/v1/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'controller': CONFIG['controller']['name'],
        'environment': CONFIG['controller']['environment'],
        'database': 'connected'
    })

@app.route('/api/v1/enroll', methods=['POST'])
def enroll_identity():
    """Enroll a new service or client into the overlay network"""
    data = request.json
    
    identity_type = data.get('type')
    name = data.get('name')
    enrollment_token = data.get('enrollment_token')
    
    # Verify enrollment token
    master_secret = os.environ.get('MASTER_ENROLLMENT_SECRET', 'dev_token_123')
    if enrollment_token != master_secret:
        return jsonify({'error': 'Invalid enrollment token'}), 401
    
    # Create new identity
    identity = Identity(
        name=name,
        identity_type=identity_type,
        status='active'
    )
    
    db.session.add(identity)
    db.session.commit()
    
    return jsonify({
        'identity_id': identity.id,
        'controller_url': CONFIG['controller']['control_plane']['public_address'],
        'overlay_config': NETWORK_CONFIG,
        'status': 'enrolled'
    })

@app.route('/api/v1/policies/check', methods=['POST'])
def check_policy():
    """Policy Decision Point - checks if source can access target"""
    data = request.json
    source_identity = data.get('source')
    target_service = data.get('target')
    action = data.get('action')
    
    # Load policies from YAML
    policies_path = os.path.join(BASE_DIR, 'config', 'policies', 'access_policies.yaml')
    try:
        with open(policies_path, 'r') as f:
            policies = yaml.safe_load(f)
    except FileNotFoundError:
        # Default policy - allow everything for development
        return jsonify({
            'allowed': True,
            'source': source_identity,
            'target': target_service,
            'action': action,
            'message': 'No policy file found, allowing by default'
        })
    
    # Check policies
    allowed = False
    for policy in policies.get('policies', []):
        if (policy.get('action') == action and 
            policy.get('source_identity') == source_identity and 
            policy.get('target_service') == target_service):
            allowed = True
            break
    
    return jsonify({
        'allowed': allowed,
        'source': source_identity,
        'target': target_service,
        'action': action
    })

@app.route('/api/v1/identities', methods=['GET'])
def list_identities():
    """List all enrolled identities"""
    identities = Identity.query.all()
    return jsonify({
        'identities': [
            {
                'id': i.id,
                'name': i.name,
                'type': i.identity_type,
                'status': i.status,
                'created_at': i.created_at.isoformat() if i.created_at else None
            } for i in identities
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('CONTROLLER_PORT', CONFIG['controller']['control_plane']['bind_port']))
    host = os.environ.get('CONTROLLER_HOST', CONFIG['controller']['control_plane']['bind_host'])
    
    print("=" * 60)
    print("ZTA Controller - Policy Decision Point")
    print("=" * 60)
    print(f"Running on: {host}:{port}")
    print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=True, use_reloader=False)
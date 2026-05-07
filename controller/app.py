import os
import yaml
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Load environment variables - NO HARDCODES
load_dotenv()

# Load configuration from YAML
with open('config/controller_config.yaml', 'r') as f:
    CONFIG = yaml.safe_load(f)

with open('config/network_config.yaml', 'r') as f:
    NETWORK_CONFIG = yaml.safe_load(f)

app = Flask(__name__)

# Configure from environment and config files - NO HARDCODES
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Import models
from models import Identity, ServicePolicy, ActiveSession

@app.route('/api/v1/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'controller': CONFIG['controller']['name'],
        'environment': CONFIG['controller']['environment']
    })

@app.route('/api/v1/enroll', methods=['POST'])
def enroll_identity():
    """
    Enroll a new service or client into the overlay network
    No hardcoded values - all from config
    """
    data = request.json
    
    # Required fields from request
    identity_type = data.get('type')  # 'service' or 'client'
    name = data.get('name')
    enrollment_token = data.get('enrollment_token')
    
    # Verify enrollment token against config
    master_secret = os.environ.get('MASTER_ENROLLMENT_SECRET')
    if enrollment_token != master_secret:
        return jsonify({'error': 'Invalid enrollment token'}), 401
    
    # Create new identity
    identity = Identity(
        name=name,
        identity_type=identity_type,
        status='pending'
    )
    
    db.session.add(identity)
    db.session.commit()
    
    # Return config for the new identity (from YAML files)
    return jsonify({
        'identity_id': identity.id,
        'controller_url': CONFIG['controller']['control_plane']['public_address'],
        'overlay_config': NETWORK_CONFIG
    })

@app.route('/api/v1/policies/check', methods=['POST'])
def check_policy():
    """
    Policy Decision Point - checks if source can access target
    All policies loaded from YAML - no hardcodes
    """
    data = request.json
    source_identity = data.get('source')
    target_service = data.get('target')
    action = data.get('action')  # 'dial' or 'bind'
    
    # Load policies from YAML
    with open('config/policies/access_policies.yaml', 'r') as f:
        policies = yaml.safe_load(f)
    
    # Check policies
    allowed = False
    for policy in policies['policies']:
        if (policy['action'] == action and 
            policy['source_identity'] == source_identity and 
            policy['target_service'] == target_service):
            allowed = True
            break
    
    return jsonify({
        'allowed': allowed,
        'source': source_identity,
        'target': target_service,
        'action': action
    })

if __name__ == '__main__':
    port = int(os.environ.get('CONTROLLER_PORT', CONFIG['controller']['control_plane']['bind_port']))
    host = os.environ.get('CONTROLLER_HOST', CONFIG['controller']['control_plane']['bind_host'])
    
    app.run(host=host, port=port, debug=True)
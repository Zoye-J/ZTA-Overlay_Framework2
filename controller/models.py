#controller/models.py

from app import db
from datetime import datetime

class Identity(db.Model):
    """Represents a service or client in the overlay network"""
    __tablename__ = 'identities'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    identity_type = db.Column(db.String(20), nullable=False)  # 'service' or 'client'
    certificate_serial = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')  # 'pending', 'active', 'revoked'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime)
    
    # Relationships
    policies = db.relationship('ServicePolicy', backref='identity', lazy=True)
    sessions = db.relationship('ActiveSession', backref='identity', lazy=True)

class ServicePolicy(db.Model):
    """Policies defining who can access what services"""
    __tablename__ = 'service_policies'
    
    id = db.Column(db.Integer, primary_key=True)
    identity_id = db.Column(db.Integer, db.ForeignKey('identities.id'))
    target_service = db.Column(db.String(100))
    action = db.Column(db.String(20))  # 'dial' or 'bind'
    is_active = db.Column(db.Boolean, default=True)
    
    # Policy conditions (stored as JSON)
    conditions = db.Column(db.JSON)

class ActiveSession(db.Model):
    """Tracks active connections in the overlay"""
    __tablename__ = 'active_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    identity_id = db.Column(db.Integer, db.ForeignKey('identities.id'))
    session_token = db.Column(db.String(500))
    connected_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    client_ip = db.Column(db.String(50))  # Real IP, not overlay IP
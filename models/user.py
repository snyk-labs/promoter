"""
User model for authentication and profile information.
"""

from datetime import datetime
import bcrypt
from flask_login import UserMixin
from extensions import db
from sqlalchemy import text

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)  # Now nullable for SSO users
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bio = db.Column(db.Text, nullable=True)
    
    # Authentication source - using server_default for SQLite compatibility
    auth_type = db.Column(db.String(20), nullable=False, server_default=text("'password'"))
    
    # Okta user identifier
    okta_id = db.Column(db.String(100), nullable=True, unique=True)
    
    # Arcade LinkedIn integration field
    linkedin_authorized = db.Column(db.Boolean, default=False, nullable=False)
    
    # Arcade X integration field
    x_authorized = db.Column(db.Boolean, default=False, nullable=False)
    
    # Autonomous mode for automatic posting
    autonomous_mode = db.Column(db.Boolean, default=False, nullable=False)
    
    def set_password(self, password):
        """Hash password with bcrypt using work factor 13."""
        salt = bcrypt.gensalt(rounds=13)
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, password):
        """Check if provided password matches the hash."""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    @classmethod
    def find_or_create_okta_user(cls, okta_id, email, name):
        """Find existing user by Okta ID or create a new one."""
        user = cls.query.filter_by(okta_id=okta_id).first()
        if user:
            return user
            
        # Check if a user exists with this email but no Okta ID (existing user now using SSO)
        existing_user = cls.query.filter_by(email=email).first()
        if existing_user:
            # Update existing user with Okta ID
            existing_user.okta_id = okta_id
            existing_user.auth_type = 'okta'
            return existing_user
            
        # Create new user
        user = cls(
            email=email,
            name=name,
            auth_type='okta',
            okta_id=okta_id
        )
        db.session.add(user)
        db.session.commit()
        return user
    
    def __repr__(self):
        return f'<User {self.email}>' 
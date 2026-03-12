"""
JWT Authentication Handler for ClerKase
"""

import os
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

# JWT Configuration
JWT_SECRET = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24


def generate_token(user_id: int, email: str, username: str) -> str:
    """
    Generate JWT token for user
    
    Args:
        user_id: User ID
        email: User email
        username: Username
        
    Returns:
        JWT token string
    """
    payload = {
        'user_id': user_id,
        'email': email,
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """
    Decorator to require JWT token for endpoint
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        # Verify token
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Token is invalid or expired'}), 401
        
        # Add user info to request
        request.current_user = payload
        
        return f(*args, **kwargs)
    
    return decorated


def get_current_user() -> dict:
    """
    Get current user from request context
    Must be used within a route decorated with @token_required
    
    Returns:
        User payload dict
    """
    return getattr(request, 'current_user', None)

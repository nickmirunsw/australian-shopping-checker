"""
Simple admin authentication system.
"""

import hashlib
import secrets
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Simple in-memory session store (in production, use Redis or database)
_active_sessions = {}

# Admin credentials (in production, use environment variables and proper hashing)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password"

# Session timeout (30 minutes)
SESSION_TIMEOUT = timedelta(minutes=30)


def authenticate_admin(username: str, password: str) -> Optional[str]:
    """
    Authenticate admin user and return session token if successful.
    
    Args:
        username: Admin username
        password: Admin password
        
    Returns:
        Session token if authentication successful, None otherwise
    """
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        
        # Store session with expiration
        _active_sessions[session_token] = {
            'username': username,
            'created_at': datetime.now(),
            'last_accessed': datetime.now()
        }
        
        logger.info(f"Admin user authenticated successfully, session: {session_token[:8]}...")
        return session_token
    
    logger.warning(f"Failed admin authentication attempt for username: {username}")
    return None


def validate_admin_session(session_token: str) -> bool:
    """
    Validate if session token is valid and not expired.
    
    Args:
        session_token: Session token to validate
        
    Returns:
        True if session is valid, False otherwise
    """
    if not session_token or session_token not in _active_sessions:
        return False
    
    session = _active_sessions[session_token]
    now = datetime.now()
    
    # Check if session has expired
    if now - session['last_accessed'] > SESSION_TIMEOUT:
        logger.info(f"Admin session expired: {session_token[:8]}...")
        del _active_sessions[session_token]
        return False
    
    # Update last accessed time
    session['last_accessed'] = now
    return True


def logout_admin(session_token: str) -> bool:
    """
    Logout admin user by invalidating session.
    
    Args:
        session_token: Session token to invalidate
        
    Returns:
        True if session was found and invalidated, False otherwise
    """
    if session_token in _active_sessions:
        logger.info(f"Admin user logged out, session: {session_token[:8]}...")
        del _active_sessions[session_token]
        return True
    return False


def cleanup_expired_sessions():
    """Clean up expired sessions."""
    now = datetime.now()
    expired_sessions = []
    
    for token, session in _active_sessions.items():
        if now - session['last_accessed'] > SESSION_TIMEOUT:
            expired_sessions.append(token)
    
    for token in expired_sessions:
        logger.info(f"Cleaning up expired session: {token[:8]}...")
        del _active_sessions[token]
    
    if expired_sessions:
        logger.info(f"Cleaned up {len(expired_sessions)} expired admin sessions")


def get_active_sessions_count() -> int:
    """Get count of active admin sessions."""
    cleanup_expired_sessions()  # Clean up first
    return len(_active_sessions)


def is_admin_authenticated(session_token: Optional[str]) -> bool:
    """
    Check if the provided session token represents an authenticated admin.
    
    Args:
        session_token: Session token from request
        
    Returns:
        True if admin is authenticated, False otherwise
    """
    if not session_token:
        return False
    
    return validate_admin_session(session_token)
"""
Simple admin authentication system.
"""

import hashlib
import secrets
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Session store - use database in production, memory for local development
import os
_active_sessions = {}  # Fallback for local development

def get_session_storage():
    """Get session storage - database in production, memory locally."""
    if os.getenv("DATABASE_URL"):  # Production
        try:
            from .db_config import get_db_connection
            return "database"
        except:
            return "memory"
    return "memory"

def store_session_db(session_token: str, session_data: dict):
    """Store session in database."""
    try:
        from .db_config import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Create sessions table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    session_token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    last_accessed TIMESTAMP NOT NULL
                )
            """)
            
            # Insert/update session
            cursor.execute("""
                INSERT INTO admin_sessions (session_token, username, created_at, last_accessed)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_token) 
                DO UPDATE SET last_accessed = EXCLUDED.last_accessed
            """, (
                session_token,
                session_data['username'],
                session_data['created_at'],
                session_data['last_accessed']
            ))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to store session in database: {e}")
        # Fallback to memory
        _active_sessions[session_token] = session_data

def get_session_db(session_token: str):
    """Get session from database."""
    try:
        from .db_config import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT username, created_at, last_accessed 
                FROM admin_sessions 
                WHERE session_token = %s
            """, (session_token,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'username': row[0],
                    'created_at': row[1],
                    'last_accessed': row[2]
                }
    except Exception as e:
        logger.error(f"Failed to get session from database: {e}")
        # Fallback to memory
        return _active_sessions.get(session_token)
    
    return None

def delete_session_db(session_token: str):
    """Delete session from database."""
    try:
        from .db_config import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admin_sessions WHERE session_token = %s", (session_token,))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to delete session from database: {e}")
        # Fallback to memory
        _active_sessions.pop(session_token, None)

def cleanup_expired_sessions_db():
    """Clean up expired sessions from database."""
    try:
        from .db_config import get_db_connection
        cutoff_time = datetime.now() - SESSION_TIMEOUT
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admin_sessions WHERE last_accessed < %s", (cutoff_time,))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {e}")
        # Fallback to memory cleanup
        cutoff_time = datetime.now() - SESSION_TIMEOUT
        expired_tokens = [
            token for token, data in _active_sessions.items()
            if data['last_accessed'] < cutoff_time
        ]
        for token in expired_tokens:
            _active_sessions.pop(token, None)

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
        session_data = {
            'username': username,
            'created_at': datetime.now(),
            'last_accessed': datetime.now()
        }
        
        # Use database storage in production, memory locally
        if get_session_storage() == "database":
            store_session_db(session_token, session_data)
        else:
            _active_sessions[session_token] = session_data
        
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
    if not session_token:
        return False
    
    # Get session from database or memory
    if get_session_storage() == "database":
        session = get_session_db(session_token)
    else:
        session = _active_sessions.get(session_token)
    
    if not session:
        return False
    
    now = datetime.now()
    
    # Check if session has expired
    if now - session['last_accessed'] > SESSION_TIMEOUT:
        logger.info(f"Admin session expired: {session_token[:8]}...")
        # Remove expired session
        if get_session_storage() == "database":
            delete_session_db(session_token)
        else:
            _active_sessions.pop(session_token, None)
        return False
    
    # Update last accessed time
    session['last_accessed'] = now
    if get_session_storage() == "database":
        store_session_db(session_token, session)
    else:
        _active_sessions[session_token] = session
    
    return True


def logout_admin(session_token: str) -> bool:
    """
    Logout admin user by invalidating session.
    
    Args:
        session_token: Session token to invalidate
        
    Returns:
        True if session was found and invalidated, False otherwise
    """
    # Check if session exists
    if get_session_storage() == "database":
        session = get_session_db(session_token)
        if session:
            logger.info(f"Admin user logged out, session: {session_token[:8]}...")
            delete_session_db(session_token)
            return True
    else:
        if session_token in _active_sessions:
            logger.info(f"Admin user logged out, session: {session_token[:8]}...")
            del _active_sessions[session_token]
            return True
    
    return False


def cleanup_expired_sessions():
    """Clean up expired sessions."""
    if get_session_storage() == "database":
        cleanup_expired_sessions_db()
    else:
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
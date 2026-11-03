"""
Authentication & JWT Security Service
Handles password hashing, token creation/decryption, user registration,
and FastAPI security dependencies.
"""

import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database.models import User, SessionLocal

# Security Config
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    # Development fallback only; production deployments must configure a secret.
    SECRET_KEY = "development-only-change-this-secret"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_auth_db():
    """Provide and reliably close a database session for auth dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Password Hashing ───────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hashes a raw password string using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


# ─── JWT Token Management ───────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        print("JWT Token expired")
        return None
    except jwt.PyJWTError as e:
        print(f"JWT Token decode error: {e}")
        return None


# ─── Auth Dependencies ──────────────────────────────────────────────────────

def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_auth_db)
) -> Optional[User]:
    """
    Returns current authenticated User if a valid token is provided,
    or None if no token or invalid token. (Non-blocking fallback)
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    user_id = payload.get("sub")
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
    except Exception:
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_auth_db)
) -> User:
    """
    Strict dependency: Requires a valid JWT bearer token.
    Throws 401 Unauthorized if invalid or missing.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or missing auth token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise credentials_exception
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    return user


# ─── Default Admin Seeding ──────────────────────────────────────────────────

def seed_default_admin(db: Session):
    """Seed an explicitly configured bootstrap admin for local development only."""
    try:
        admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
        admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
        if not admin_email or not admin_password:
            return
        existing = db.query(User).filter(User.email == admin_email).first()
        if not existing:
            default_user = User(
                email=admin_email,
                hashed_password=hash_password(admin_password),
                full_name="Sports Media Admin",
                role="admin",
                is_active=True
            )
            db.add(default_user)
            db.commit()
            print(f"Configured bootstrap admin created: {admin_email}")
    except Exception as e:
        print(f"Error seeding admin: {e}")

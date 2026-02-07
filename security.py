# security.py
import os, secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette import status

from jose import jwt, JWTError, ExpiredSignatureError  # ← use python-jose only
from passlib.context import CryptContext

from database import SessionLocal, User

security = HTTPBearer()

# ── JWT config ────────────────────────────────────────────────────────────────
# IMPORTANT: set JWT_SECRET_KEY in your env so tokens survive restarts
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"

# ── Password hashing ─────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ── Auth helpers ─────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Return username (sub) if token is valid; else raise 401."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token")

        db = SessionLocal()
        try:
            # Match by email now
            user = db.query(User).filter(User.email == sub).first()
        finally:
            db.close()

        if not user:
            raise HTTPException(status_code=401, detail="User no longer exists")

        return user.email  # return the email

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        # Any other token problem (bad signature, malformed, etc.)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def authenticate_user(username: str, password: str) -> bool:
    """Check username/password against the DB."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return False
        return verify_password(password, user.password_hash)
    finally:
        db.close()

EMAIL_VERIFY_AUDIENCE = "email-verify"
EMAIL_VERIFY_TTL_MIN = int(os.getenv("EMAIL_VERIFY_TTL_MIN", "60"))  # 60 minutes

def create_email_verify_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=EMAIL_VERIFY_TTL_MIN)
    payload = {
        "sub": str(user_id),
        "email": email,
        "aud": EMAIL_VERIFY_AUDIENCE,
        "exp": expire,
        "typ": "email_verify",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_email_verify_token(token: str) -> dict:
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], audience=EMAIL_VERIFY_AUDIENCE)
        if data.get("typ") != "email_verify":
            raise JWTError("Wrong token type")
        return data
    except JWTError as e:
        raise HTTPException(status_code=400, detail=f"Invalid or expired verification token: {e}")

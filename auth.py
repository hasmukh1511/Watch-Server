import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

# Environment variables - REQUIRED in production
SECRET_KEY = os.environ["SECRET_KEY"]  # Must be set in production
ALGORITHM = os.environ.get("ALGORITHM", "HS256")

# Token blacklist for logout functionality
token_blacklist = set()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# User database
users_db = {
    "Perents1511": {
        "username": "Perents1511",
        "full_name": "Parent User",
        "hashed_password": pwd_context.hash("Splender@#1511"),
        "role": "parent"
    }
}

# Add child users (1 to 30)
for i in range(1, 31):
    username = f"chaild{i}"
    users_db[username] = {
        "username": username,
        "full_name": f"Child User {i}",
        "hashed_password": pwd_context.hash("Splender#@9750"),
        "role": "child"
    }

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(username: str, password: str):
    if username not in users_db:
        return False
    user = users_db[username]
    if not verify_password(password, user["hashed_password"]):
        return False
    return user

def create_access_token(data: dict):
    user_role = data.get("role", "")
    
    # Different expiry for child vs parent
    if user_role == "child":
        # Child devices: 365 days (1 year)
        expires_delta = timedelta(days=365)
    else:
        # Parent devices: 7 days
        expires_delta = timedelta(days=7)
    
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        # Check if token is blacklisted
        if token in token_blacklist:
            return None
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
            
        # Check if token is expired
        expire_timestamp = payload.get("exp")
        if expire_timestamp and datetime.utcnow().timestamp() > expire_timestamp:
            return None
            
        return users_db.get(username)
    except JWTError:
        return None
import json
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

# Secret key for encoding and decoding JWT tokens
SECRET_KEY = "asfe@#147gfhrt%$#de1#1fr#$54frjg"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# User database (in production, use a real database)
users_db = {
    "Perents1511": {
        "username": "Perents1511",
        "full_name": "Parent User",
        "hashed_password": pwd_context.hash("Splender@#1511"),
        "role": "parent"
    }
}

# Add child users
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

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return users_db.get(username)
    except JWTError:
        return None
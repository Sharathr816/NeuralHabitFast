import secrets
import hashlib
from database.models import User
from database.schema import AuthResponse

# ---------- Password helpers ----------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return f"{salt.hex()}${hashed.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
        return secrets.compare_digest(candidate, expected)
    except Exception:
        return False

def user_to_response(user: User) -> AuthResponse:
    return AuthResponse(
        user_id=user.user_id,
        name=user.username,
        email=user.email,
        signup_date=user.signup_at,
    )
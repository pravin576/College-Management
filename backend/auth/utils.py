import hashlib
import time

def hash_password(password: str) -> str:
    salt = hashlib.sha256(str(time.time()).encode('utf-8')).hexdigest()[:16]
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}${key.hex()}"

def verify_password(stored_password: str, provided_password: str) -> bool:
    if not stored_password or not provided_password:
        return False
    if "$" not in stored_password:
        return stored_password == provided_password
    salt, key_hex = stored_password.split("$", 1)
    key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return key.hex() == key_hex

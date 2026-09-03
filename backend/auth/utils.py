import hashlib
import time
import secrets
import string

def generate_temp_password(length=9) -> str:
    """Generate a secure, random temporary password (e.g. Tmp8#K2x9)"""
    digits = string.digits
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    symbols = "!@#$%^&*"
    pwd = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(symbols)
    ]
    all_chars = uppercase + lowercase + digits + symbols
    for _ in range(max(length - 4, 4)):
        pwd.append(secrets.choice(all_chars))
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)

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

from backend.core.security import verify_password
import bcrypt

has_pass = bcrypt.hashpw(b"staff@123",bcrypt.gensalt())
print(has_pass)
stored_hash = has_pass

print(verify_password("staff@123", stored_hash))
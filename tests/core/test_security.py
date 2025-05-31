from tests.conftest import settings
from jose import jwt
from app.core.security import ALGORITHM,verify_password, get_password_hash, create_access_token, get_current_user

def test_get_and_verify_password():
  password = "test_password"
  hashed_password = get_password_hash(password)
  assert verify_password(password, hashed_password)
  assert not verify_password("wrong_password", hashed_password)

def test_create_access_token():
  user_id = "1"
  role = "admin"
  token = create_access_token({"sub": user_id, "role": role})
  assert type(token) == str
  payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
  assert payload.get("sub") == user_id
  assert payload.get("role") == role

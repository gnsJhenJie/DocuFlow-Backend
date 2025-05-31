from tests.conftest import settings, db_add
from jose import jwt
from app.db.models import User
from app.db.session import get_db
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

def test_get_current_user():
  user_id = 1
  role = "admin"
  added_user = User(
    id=user_id,
    role=role,
    email="",
    hashed_password="",
    name=""
  )
  db_add(added_user)

  data = {
    "sub": str(user_id),
    "role": role
  }
  token = create_access_token(data)
  user = get_current_user(token=token, db=next(get_db()))
  print(user)
  assert user.id == user_id
  assert user.role == role
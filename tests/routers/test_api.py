from tests.conftest import db_add
from app.db.models import User
from app.core.security import get_password_hash

def test_login_and_me(client):
    name = "test_login"
    email = "test_login@example.com"
    password = "test_login_password"
    hash_password = get_password_hash(password)
    wrong_password = "wrong_password"
    role = "viewer"
    user = User(
        id = 1,
        email = email,
        hashed_password = hash_password,
        name = name,
        role = role,
    )
    db_add(user)
    
    data = {
        "username": email,
        "password": wrong_password,
    }
    data_login_failed = client.post("/api/auth/login", data=data)
    assert data_login_failed.status_code == 401
    assert data_login_failed.json()["detail"] == "Invalid credentials"

    data = {
        "username": email,
        "password": password,
    }
    data_login = client.post("/api/auth/login", data=data)
    user = data_login.json()["user"]
    assert data_login.status_code == 200
    assert user["email"] == email
    assert user["name"] == name
    assert user["role"] == role
    assert "hashed_password" not in user
    token = data_login.json()["token"]
    assert token != ""
    
    headers = {"Authorization": f"Bearer {token}"}
    data_me = client.get("/api/auth/me", headers=headers)
    print(data_me.json())
    assert data_me.status_code == 200
    me = data_me.json()
    assert me["email"] == email

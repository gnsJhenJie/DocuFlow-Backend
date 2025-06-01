from tests.conftest import db_add
from app.db.models import User
from app.core.security import get_password_hash

def test_login_api(client):
    name = "test_login"
    email = "test_login@example.com"
    password = "test_login_password"
    hash_password = get_password_hash(password)
    wrong_password = "wrong_password"
    role = "viewer"
    user = User(
        email = email,
        hashed_password = hash_password,
        name = name,
        role = role,
    )
    db_add(user)
    
    data = {
        "email": email,
        "password": password,
        "name": name,
        "role": role
    }
    response = client.post("/api/auth/login", json=data)
    response_user = response.json()["user"]
    print(response_user)
    assert response.status_code == 200
    assert response_user["email"] == email
    assert response_user["name"] == name
    assert response_user["role"] == role
    assert "hashed_password" not in response_user

    data = {
        "email": email,
        "password": wrong_password,
        "name": name,
        "role": role
    }
    response = client.post("/api/auth/login", json=data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

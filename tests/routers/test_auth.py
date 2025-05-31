from tests.conftest import db_add
from app.db.models import User
from app.core.security import get_password_hash


def test_login(client):
    name = "test_login"
    email = "test_login@test.com"
    password = "test_login_password"
    wrong_password = "wrong_password"
    role = "viewer"
    user = User(
        email = email,
        hashed_password = get_password_hash(password),
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
    assert response.status_code == 200

    data = {
        "email": email,
        "password": wrong_password,
        "name": name,
        "role": role
    }
    assert client.post("/api/auth/login", json=data).status_code == 401

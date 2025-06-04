from tests.conftest import db_add
from app.db.models import User
from app.core.security import get_password_hash

def register(id: int = 1, email: str = "test@example.com", password: str = "secret", role: str = "viewer"):
    user = User(
        id=id,
        email=email,
        name="Test User",
        hashed_password=get_password_hash(password),
        role=role
    )
    db_add(user)
    return user, password

def get_headers(client, email: str, password: str):
    data = {
        "username": email,
        "password": password,
    }
    data_login = client.post("/api/auth/login", data=data)
    assert data_login.status_code == 200
    token = data_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers


def test_login_and_me(client):
    user, password = register()
    wrong_password = "wrong_password"
    
    data = {
        "username": user.email,
        "password": wrong_password,
    }
    data_login_failed = client.post("/api/auth/login", data=data)
    assert data_login_failed.status_code == 401
    assert data_login_failed.json()["detail"] == "Invalid credentials"

    data = {
        "username": user.email,
        "password": password,
    }
    data_login = client.post("/api/auth/login", data=data)
    assert data_login.status_code == 200

    login_user = data_login.json()["user"]
    assert login_user["email"] == user.email
    assert login_user["name"] == user.name
    assert login_user["role"] == user.role
    assert "hashed_password" not in login_user

    token = data_login.json()["token"]
    assert token != ""
    
    headers = {"Authorization": f"Bearer {token}"}
    data_me = client.get("/api/auth/me", headers=headers)
    assert data_me.status_code == 200
    me = data_me.json()
    assert me["email"] == user.email


def test_user_roles_and_list(client):
    user, password = register(
        id=1,
        email="admin@example.com",
        password="adminpass",
        role="admin"
    )

    headers = get_headers(client, user.email, password)

    # List users as admin
    response = client.get("/api/users", headers=headers)
    assert response.status_code == 200
    users = response.json()
    assert len(users) == 1

    # List reviewers (none initially)
    response = client.get("/api/users/reviewers", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    response = client.put(f"/api/users/{user.id}/role", json={"role": "reviewer"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "reviewer"

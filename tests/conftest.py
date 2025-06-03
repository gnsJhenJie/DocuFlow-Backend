import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Iterable

import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ensure the test environment uses a SQLite in-memory database
from app.core.config import settings

# Override DATABASE_URL for tests
settings.DATABASE_URL = "sqlite:///./tests/test.db"

from app.db.base import Base
from app.db.session import engine
from app.main import app

# Check pytest plugins
pytest_plugins = ("pytest_mock",)

# Drop and recreate all tables before each test
@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def db_add(data):
    with Session(engine) as session:
        session.add(data)
        session.commit()
        session.refresh(data)

def db_add_all(data: Iterable):
    with Session(engine) as session:
        for d in data:
            session.add(d)
        session.commit()
        for d in data:
            session.refresh(d)

# tests/test_api.py

def test_register_and_login_and_me(client):
    # Register
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "secret",
        "name": "Test User"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "test@example.com"
    token = data["token"]

    # Login
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "secret"
    })
    assert response.status_code == 200
    data_login = response.json()
    assert data_login["user"]["email"] == "test@example.com"
    token_login = data_login["token"]
    assert token_login != ""

    # Get current user
    headers = {"Authorization": f"Bearer {token_login}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    me = response.json()
    assert me["email"] == "test@example.com"


def test_user_roles_and_list(client):
    # Register admin user
    response = client.post("/api/auth/register", json={
        "email": "admin@example.com",
        "password": "adminpass",
        "name": "Admin User",
        "role": "admin"
    })
    assert response.status_code == 200
    admin_token = response.json()["token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # List users as admin
    response = client.get("/api/users", headers=headers)
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 2  # test and admin users

    # List reviewers (none initially)
    response = client.get("/api/users/reviewers", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # Promote test user to reviewer
    test_user = next(u for u in users if u["email"] == "test@example.com")
    response = client.put(f"/api/users/{test_user['id']}/role", json={"role": "reviewer"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "reviewer"


def test_document_crud_and_workflow(client):
    # Login as editor
    client.post("/api/auth/register", json={"email":"ed@example.com","password":"edpass","name":"Editor","role":"editor"})
    login = client.post("/api/auth/login", json={"email":"ed@example.com","password":"edpass"}).json()
    editor_token = login["token"]
    ed_headers = {"Authorization": f"Bearer {editor_token}"}

    # Create draft
    response = client.post("/api/documents", json={
        "title": "Doc1",
        "content": "Content1",
        "action": "save_draft"
    }, headers=ed_headers)
    assert response.status_code == 200
    doc = response.json()
    doc_id = doc["id"]
    assert doc["status"] == "draft"

    # Submit for review (assign to reviewer)
    # First, ensure a reviewer exists
    admin_login = client.post("/api/auth/login", json={"email":"admin@example.com","password":"adminpass"}).json()
    admin_token = admin_login["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    reviewers = client.get("/api/users/reviewers", headers=admin_headers).json()
    reviewer_id = reviewers[0]["id"]

    response = client.put(f"/api/documents/{doc_id}", json={
        "action": "resubmit_for_review",
        "reviewerId": reviewer_id
    }, headers=ed_headers)
    assert response.status_code == 200
    submitted = response.json()
    assert submitted["status"] == "pending_review"
    assert submitted["reviewerId"] == reviewer_id

    # Reviewer approves
    # Login as reviewer
    rev_login = client.post("/api/auth/login", json={"email":"test@example.com","password":"secret"}).json()
    rev_token = rev_login["token"]
    rev_headers = {"Authorization": f"Bearer {rev_token}"}
    response = client.post(f"/api/documents/{doc_id}/approve", headers=rev_headers)
    assert response.status_code == 200
    approved = response.json()
    assert approved["status"] == "approved"

    # Check history
    response = client.get(f"/api/documents/{doc_id}/history", headers=ed_headers)
    assert response.status_code == 200
    history = response.json()
    actions = [h["action"] for h in history]
    assert any(a == "approved" for a in actions)


# def test_image_upload(client):
#     # Login as editor
#     login = client.post("/api/auth/login", json={"email":"ed@example.com","password":"edpass"}).json()
#     token = login["token"]
#     headers = {"Authorization": f"Bearer {token}"}

#     # Upload a small dummy image file
#     file_content = b"\x47\x49\x46\x38\x39\x61"  # GIF header
#     files = {"file": ("test.gif", file_content, "image/gif")}
#     response = client.post("/api/upload", files=files)
#     assert response.status_code == 200
#     data = response.json()
#     assert data.get("imageUrl").startswith("https://")
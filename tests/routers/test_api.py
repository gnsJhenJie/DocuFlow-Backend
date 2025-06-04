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


def test_document_crud_and_workflow(client, mocker):
    mocker.patch("app.routers.documents.queue_review_email", return_value=None)
    editor, editor_password = register(
        id=1,
        email="editor@example.com",
        password="editorpass",
        role="editor"
    )
    admin, admin_password = register(
        id=2,
        email="admin@example.com",
        password="adminpass",
        role="admin"
    )
    reviewer, reviewer_password = register(
        id=3,
        email="reviewer@example.com",
        password="reviewerpass",
        role="reviewer"
    )


    editor_headers = get_headers(client, editor.email, editor_password)
    # Create draft
    response = client.post("/api/documents", json={
        "title": "Doc1",
        "content": "Content1",
        "action": "save_draft"
    }, headers=editor_headers)
    assert response.status_code == 200
    doc = response.json()
    doc_id = doc["id"]
    assert doc["status"] == "draft"

    # Submit for review (assign to reviewer)
    # First, ensure a reviewer exists
    admin_headers = get_headers(client, admin.email, admin_password)
    reviewers = client.get("/api/users/reviewers", headers=admin_headers).json()
    
    response = client.put(f"/api/documents/{doc_id}", json={
        "action": "resubmit_for_review",
        "reviewerId": reviewer.id
    }, headers=editor_headers)
    assert response.status_code == 200
    submitted = response.json()
    assert submitted["status"] == "pending_review"
    assert submitted["reviewerId"] == reviewer.id

    # Reviewer approves
    # Login as reviewer
    reviewer_headers = get_headers(client, reviewer.email, reviewer_password)
    response = client.post(f"/api/documents/{doc_id}/approve", headers=reviewer_headers)
    assert response.status_code == 200
    approved = response.json()
    assert approved["status"] == "approved"

    # Check history
    response = client.get(f"/api/documents/{doc_id}/history", headers=editor_headers)
    assert response.status_code == 200
    history = response.json()
    actions = [h["action"] for h in history]
    assert any(a == "approved" for a in actions)

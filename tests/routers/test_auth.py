from pydantic import EmailStr
from fastapi import HTTPException
from tests.conftest import db_add
from app.db.models import User, Role
from app.schemas.user import UserCreate
from app.db.session import get_db
from app.core.security import get_password_hash
from app.routers.auth import login


def test_login():
    name = "test_login"
    email = "test_login@example.com"
    email_str = EmailStr(email)
    password = "test_login_password"
    hash_password = get_password_hash(password)
    wrong_password = "wrong_password"
    role = Role.admin
    user = User(
        email=email,
        hashed_password=hash_password,
        name=name,
        role=role.value,
    )
    db_add(user)
    
    data = UserCreate(
        email=email_str,
        password=password,
        name=name,
        role=role
    )
    result = login(data=data, db=next(get_db()))
    assert result["user"].email == email    
    assert result["user"].hashed_password == hash_password
    assert result["user"].name == name
    assert result["user"].role == role

    data = UserCreate(
        email=email_str,
        password=wrong_password,
        name=name,
        role=role
    )
    try:
        login(data=data, db=next(get_db()))
        assert False, "Should raise HTTPException"
    except HTTPException as e:
        assert e.status_code == 401
        assert e.detail == "Invalid credentials"

from sqlalchemy.orm import Session
from pydantic import EmailStr
from fastapi import HTTPException
from tests.conftest import db_add
from app.db.models import User, Role
from fastapi.security import OAuth2PasswordRequestForm
from app.db.session import engine
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
    
    data = OAuth2PasswordRequestForm(
        username=email_str,
        password=password,
    )
    data_error = OAuth2PasswordRequestForm(
        username=email_str,
        password=wrong_password,
    )

    with Session(engine) as db:
        result = login(form_data=data, db=db)
        assert result["user"].email == email    
        assert result["user"].hashed_password == hash_password
        assert result["user"].name == name
        assert result["user"].role == role

        try:
            login(form_data=data_error, db=db)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 401
            assert e.detail == "Invalid credentials"

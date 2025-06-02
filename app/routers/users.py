from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.db.models import User, Role
from app.schemas.user import UserRead
from app.core.security import require_role

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserRead])
def list_users(
    role: Role | None = None,
    db: Session = Depends(get_db),
    current=Depends(require_role(Role.admin)),
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.all()


@router.get("/reviewers", response_model=List[UserRead])
def list_reviewers(
    db: Session = Depends(get_db),
    current=Depends(require_role(Role.admin, Role.editor, Role.reviewer)),
):
    return db.query(User).filter(User.role.in_([Role.reviewer, Role.admin])).all()


@router.put("/{user_id}/role", response_model=UserRead)
def update_role(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current=Depends(require_role(Role.admin)),
):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.role = Role(payload.get("role"))
    db.commit()
    return user

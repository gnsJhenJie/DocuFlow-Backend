from fastapi import HTTPException
from tests.conftest import db_add_all
from app.db.models import Role, User
from app.db.session import get_db
from app.routers.users import list_users, list_reviewers, update_role

def insert_users():
    users = []
    roles = {
        Role.admin: 1,
        Role.editor: 2,
        Role.reviewer: 3,
        Role.viewer: 4
    }
    for role, cnt in roles.items():
        for _ in range(cnt):
            idx = len(users) + 1
            user = User(
                email=f"user{idx}@example.com", 
                hashed_password=f"hashed_password{idx}",
                name=f"user{idx}",
                role=role
            )
            users.append(user)
    db_add_all(users)
    return users, roles


def test_list_users():
    users, roles = insert_users()
    db = next(get_db())

    result = list_users(db=db, current=users[0])
    assert len(result) == len(users), f"There should be {len(users)} users"
    for role, cnt in roles.items():
        result = list_users(role=role, db=db, current=users[0])
        assert len(result) == cnt, f"There should be {cnt} users with role {role}"
        for user in result:
            print(user.role)
            assert user.role.value == role.value, f"{user.name} should have role {role.value}"


def test_list_reviewers():
    users, roles = insert_users()
    db = next(get_db())

    result = list_reviewers(db=db, current=users[0])
    assert len(result) == roles[Role.reviewer] + roles[Role.admin], f"There should be {roles[Role.reviewer] + roles[Role.admin]} reviewers"
    for user in result:
        assert user.role.value == Role.reviewer.value or user.role.value == Role.admin.value, f"{user.name} should have role {Role.reviewer.value} or {Role.admin.value}"


def test_update_role():
    users, _ = insert_users()
    db = next(get_db())

    user = users[1]
    assert user.role.value == Role.editor.value, f"{user.name} should have role {Role.editor.value}"
    result = update_role(user_id=user.id, payload={"role": Role.admin.value}, db=db, current=users[0])
    assert result.role.value == Role.admin.value, f"{user.name} should have role {Role.admin.value}"

    try:
        update_role(user_id=0, payload={"role": Role.admin.value}, db=next(get_db()), current=users[0])
        assert False, "Should raise HTTPException"
    except HTTPException as e:
        assert e.status_code == 404
        assert e.detail == "User not found"

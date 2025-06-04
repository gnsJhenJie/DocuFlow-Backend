from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from app.db.models import Role
from datetime import datetime


class UserBase(BaseModel):
    id: int
    email: EmailStr
    name: str
    avatarUrl: Optional[str]
    role: Role


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Optional[Role] = Role.viewer


class UserRead(UserBase):
    created_at: datetime = Field(..., alias="createdAt")

    class Config:
        orm_mode = True
        allow_population_by_field_name = True

from pydantic import BaseModel
from app.schemas.user import UserRead


class Token(BaseModel):
    token: str
    user: UserRead

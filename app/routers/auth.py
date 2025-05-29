from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserRead
from app.schemas.token import Token
from app.db.session import get_db
from app.db.models import User, Role
from app.core.security import get_password_hash, verify_password, create_access_token, get_current_user
router = APIRouter(prefix="/api/auth", tags=["auth"])
from app.core.config import settings
import httpx
from jose import jwt
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


class OAuthCallbackRequest(BaseModel):
    code: str

# --------------- Google OAuth ---------------

@router.get("/google/url")
def google_oauth_url():
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [f"{settings.FRONTEND_URL}/auth/callback"],
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ],
        redirect_uri=f"{settings.FRONTEND_URL}/auth/callback",
    )

    # 產生授權網址，並要求把已授權 scope 也一併帶進來，避免日後 scope 擴張
    auth_url, _state = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="consent"          # ← 想每次都重選帳號就保留；否則拿掉
    )
    return {"url": auth_url}


@router.post("/google/callback", response_model=Token)
async def google_callback(payload: OAuthCallbackRequest, db: Session = Depends(get_db)):
    """
    1. 用 google-auth-oauthlib 交換 `code` → Credentials  
    2. 驗證 `id_token` → 取得 email / name  
    3. 建立或取得本地使用者，簽發我們自己的 JWT  
    4. 回傳 { token, user }
    """
    code = payload.code

    # ---------- 1. 建立 Flow 並交換 token ----------
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [f"{settings.FRONTEND_URL}/auth/callback"],
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
        redirect_uri=f"{settings.FRONTEND_URL}/auth/callback",
    )

    try:
        flow.fetch_token(code=code)
    except Exception as e:
        print("fetch_token error:", e)
        raise HTTPException(status_code=400, detail=f"Google token exchange failed: {e}")

    creds = flow.credentials  # google.oauth2.credentials.Credentials
    id_token_str = creds.id_token
    if not id_token_str:
        raise HTTPException(status_code=400, detail="Google did not return id_token")

    # ---------- 2. 驗證 / 解碼 id_token ----------
    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            audience=settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        # 可能是簽章錯誤、audience 不符、過期等
        print("verify id_token error:", e) 
        raise HTTPException(status_code=401, detail=f"Invalid id_token: {e}")

    email = idinfo.get("email")
    name = idinfo.get("name") or email.split("@")[0]
    print(name, email)
    if not email:
        raise HTTPException(status_code=400, detail="Email not returned by Google")

    # ---------- 3. 查詢或建立本地使用者 ----------
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name=name,
            hashed_password=get_password_hash(email + settings.JWT_SECRET_KEY),
            role=Role.viewer,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # ---------- 4. 簽發我們自己的 JWT ----------
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"token": token, "user": user}

@router.post("/register", response_model=Token)
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(
        email=data.email, name=data.name,
        hashed_password=get_password_hash(data.password),
        role=data.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id, "role": user.role.value})
    return {"token": token, "user": user}

@router.post("/login", response_model=Token)
def login(data: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.id, "role": user.role.value})
    return {"token": token, "user": user}

@router.post("/logout")
def logout():
    return {"message": "Logged out"}

@router.get("/me", response_model=UserRead)
def read_current_user(user: User = Depends(get_current_user)):
    return user
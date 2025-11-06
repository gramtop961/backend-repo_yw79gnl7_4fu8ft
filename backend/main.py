import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import EmailStr
import secrets
from bson import ObjectId

from database import db, create_document, get_documents, get_one, update_document
from schemas import (
    UserCreate, UserLogin, Token, TokenData,
    ForgotPasswordRequest, ResetPasswordRequest,
    ActivityLog,
    ProjectInput, PortfolioInput,
)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
PRIMARY_ADMIN_EMAIL = os.getenv("PRIMARY_ADMIN_EMAIL", "myemail@domain.com").lower()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

app = FastAPI(title="PortfolioPal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        if user_id is None or email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    filter_id: Any = ObjectId(user_id) if isinstance(user_id, str) and len(user_id) == 24 else user_id
    user = db["user"].find_one({"_id": filter_id})
    if not user:
        raise credentials_exception
    user["_id"] = str(user["_id"])  # normalize
    return user


def is_admin(user: Dict[str, Any]) -> bool:
    return user.get("email", "").lower() == PRIMARY_ADMIN_EMAIL


# Auth routes
@app.post("/api/auth/signup", response_model=Token)
async def signup(payload: UserCreate, request: Request):
    existing = get_one("user", {"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = get_password_hash(payload.password)
    user_id = create_document("user", {"email": payload.email.lower(), "password": hashed, "name": payload.name or ""})
    token = create_access_token({"user_id": user_id, "email": payload.email.lower()})
    csrf = secrets.token_urlsafe(16)
    create_document("activity", {"user_id": user_id, "type": "signup", "ip": request.client.host})
    return {"access_token": token, "token_type": "bearer", "csrf_token": csrf}


@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None):
    user = get_one("user", {"email": form_data.username.lower()})
    if not user or not verify_password(form_data.password, user.get("password", "")):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token({"user_id": user["_id"], "email": user["email"]})
    csrf = secrets.token_urlsafe(16)
    create_document("activity", {"user_id": user["_id"], "type": "login", "ip": request.client.host if request else None})
    return {"access_token": token, "token_type": "bearer", "csrf_token": csrf}


@app.post("/api/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    user = get_one("user", {"email": payload.email.lower()})
    if user:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        create_document("passwordreset", {"user_id": user["_id"], "token": token, "expires_at": expires_at})
        # In a real app, send email here. For demo, return token.
        return {"message": "Reset email sent", "token": token}
    return {"message": "If an account exists, a reset email has been sent"}


@app.post("/api/auth/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    recs = get_documents("passwordreset", {"token": payload.token}, limit=1)
    if not recs:
        raise HTTPException(status_code=400, detail="Invalid token")
    rec = recs[0]
    if rec.get("expires_at") and rec["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expired")
    hashed = get_password_hash(payload.new_password)
    # convert id for matching
    filter_id = ObjectId(rec["user_id"]) if isinstance(rec["user_id"], str) and len(rec["user_id"]) == 24 else rec["user_id"]
    db["user"].update_one({"_id": filter_id}, {"$set": {"password": hashed, "updated_at": datetime.utcnow()}})
    return {"message": "Password updated"}


@app.get("/api/auth/me")
async def me(current = Depends(get_current_user)):
    data = {k: v for k, v in current.items() if k not in {"password"}}
    return data


# Admin only
@app.get("/api/admin/overview")
async def admin_overview(current = Depends(get_current_user)):
    if not is_admin(current):
        raise HTTPException(status_code=403, detail="Access denied")
    users = get_documents("user", {}, limit=1000)
    activity = get_documents("activity", {}, limit=1000)
    return {"users": users, "activity": activity}


# Activity logging helper endpoint (optional)
@app.post("/api/activity")
async def log_activity(log: ActivityLog, current = Depends(get_current_user)):
    if current["_id"] != log.user_id and not is_admin(current):
        raise HTTPException(status_code=403, detail="Forbidden")
    create_document("activity", log.dict())
    return {"ok": True}


# Existing AI endpoints (kept simple demo behavior)
@app.post("/api/ai/project-writer")
async def project_writer(payload: ProjectInput):
    text = f"Project: {payload.title}\nAudience: {payload.audience}\nTone: {payload.tone}\nTech: {', '.join(payload.technologies)}\n\n{payload.description}\n\nKey Points:\n- Impact\n- Challenges\n- Results"
    return {"result": text}


@app.post("/api/ai/portfolio")
async def portfolio(payload: PortfolioInput):
    result = {
        "hero": f"{payload.name} — {payload.role}",
        "summary": payload.summary,
        "language": payload.language,
        "tone": payload.tone,
        "projects": [
            {
                "name": p.name,
                "description": p.description,
                "blurb": "; ".join(p.highlights) if p.highlights else p.description,
                "tech": p.tech,
                "link": p.link,
            }
            for p in payload.projects
        ],
        "skills": payload.skills,
    }
    return {"result": __import__("json").dumps(result, ensure_ascii=False, indent=2)}


@app.get("/test")
async def test():
    return {"status": "ok"}

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

# Auth schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    csrf_token: str

class TokenData(BaseModel):
    user_id: str
    email: EmailStr
    is_admin: bool = False
    exp: Optional[int] = None
    csrf: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

class ActivityLog(BaseModel):
    user_id: str
    type: str
    ip: Optional[str] = None
    meta: Optional[dict] = None
    created_at: Optional[datetime] = None

# Existing AI endpoints schemas (kept lightweight here)
class ProjectInput(BaseModel):
    title: str
    description: str
    technologies: List[str] = []
    audience: str = "Hiring managers"
    tone: str = "professional"

class PortfolioProject(BaseModel):
    name: str
    description: str
    highlights: List[str] = []
    tech: List[str] = []
    link: Optional[str] = None

class PortfolioEducation(BaseModel):
    school: str
    degree: str
    period: str
    details: Optional[str] = None

class PortfolioInput(BaseModel):
    name: str
    role: str
    summary: str
    language: str = "English"
    tone: str = "confident"
    projects: List[PortfolioProject] = []
    education: List[PortfolioEducation] = []
    skills: List[str] = []

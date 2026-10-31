"""Authentication and User Management Endpoints.
Supports student onboarding, secure administrator registration with verification secrets,
and JWT token generation.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.entities import User, StudentProfile
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Access Control"])

class UserRegisterRequest(BaseModel):
    email: str = Field(..., description="Valid user email address")
    password: str = Field(..., min_length=6, description="User password (minimum 6 characters)")
    full_name: str = Field(..., min_length=2, description="User's full name")
    role: str = Field(default="student", description="'student' or 'admin'")
    admin_secret: Optional[str] = Field(default=None, description="Secret token required for admin role verification")
    
    university: Optional[str] = "University of Nairobi"
    field_of_study: Optional[str] = "Computer Science"
    degree_level: Optional[str] = "Undergraduate"
    year_of_study: Optional[int] = 1
    graduation_year: Optional[int] = 2026

class UserLoginRequest(BaseModel):
    email: str = Field(..., description="Registered email address")
    password: str = Field(..., description="Password")

class StudentProfileBrief(BaseModel):
    id: str
    university: str
    field_of_study: str
    degree_level: str
    graduation_year: Optional[int] = None

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    student_profile: Optional[StudentProfileBrief] = None
    created_at: Optional[datetime] = None

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new student or verified administrator account."""
    clean_email = payload.email.strip().lower()
    
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please log in instead."
        )
    
    target_role = payload.role.strip().lower()
    if target_role == "admin":
        if not payload.admin_secret or payload.admin_secret.strip() != settings.ADMIN_REGISTRATION_SECRET:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid administrator secret key. Administrator privileges cannot be granted."
            )
    else:
        target_role = "student"
    
    new_user = User(
        email=clean_email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name.strip(),
        role=target_role,
        is_active=True
    )
    db.add(new_user)
    db.flush()
    
    profile_brief = None
    if target_role == "student":
        existing_profile = db.query(StudentProfile).filter(StudentProfile.email == clean_email).first()
        if existing_profile:
            existing_profile.user_id = new_user.id
            existing_profile.full_name = new_user.full_name
            db.flush()
            profile_brief = StudentProfileBrief(
                id=existing_profile.id,
                university=existing_profile.university,
                field_of_study=existing_profile.field_of_study,
                degree_level=existing_profile.degree_level,
                graduation_year=existing_profile.graduation_year
            )
        else:
            profile = StudentProfile(
                user_id=new_user.id,
                email=clean_email,
                full_name=new_user.full_name,
                university=payload.university or "University in Kenya",
                field_of_study=payload.field_of_study or "General Studies",
                degree_level=payload.degree_level or "Undergraduate",
                year_of_study=payload.year_of_study or 1,
                graduation_year=payload.graduation_year or 2026
            )
            db.add(profile)
            db.flush()
            profile_brief = StudentProfileBrief(
                id=profile.id,
                university=profile.university,
                field_of_study=profile.field_of_study,
                degree_level=profile.degree_level,
                graduation_year=profile.graduation_year
            )
    
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(subject=new_user.id, role=new_user.role)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=new_user.id,
            email=new_user.email,
            full_name=new_user.full_name,
            role=new_user.role,
            student_profile=profile_brief,
            created_at=new_user.created_at
        )
    )

@router.post("/login", response_model=AuthResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email and password to receive a JWT access token."""
    clean_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email address or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated."
        )
    
    profile_brief = None
    if user.student_profile:
        p = user.student_profile
        profile_brief = StudentProfileBrief(
            id=p.id,
            university=p.university,
            field_of_study=p.field_of_study,
            degree_level=p.degree_level,
            graduation_year=p.graduation_year
        )
    
    access_token = create_access_token(subject=user.id, role=user.role)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            student_profile=profile_brief,
            created_at=user.created_at
        )
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user."""
    profile_brief = None
    if current_user.student_profile:
        p = current_user.student_profile
        profile_brief = StudentProfileBrief(
            id=p.id,
            university=p.university,
            field_of_study=p.field_of_study,
            degree_level=p.degree_level,
            graduation_year=p.graduation_year
        )
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        student_profile=profile_brief,
        created_at=current_user.created_at
    )

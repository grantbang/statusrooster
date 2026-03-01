from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.user import create_user, get_user_by_email, verify_password
from app.services.auth import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"], include_in_schema=False)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str


@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest):
    db = get_db()

    # Check if email already exists
    existing = get_user_by_email(db, req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate password length
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Create user
    user = create_user(db, req.email, req.password)

    # Generate JWT
    token = create_access_token(user_id=user["id"], email=user["email"])

    return AuthResponse(token=token, user_id=user["id"], email=user["email"])


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    db = get_db()

    # Find user
    user = get_user_by_email(db, req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate JWT
    token = create_access_token(user_id=user["id"], email=user["email"])

    return AuthResponse(token=token, user_id=user["id"], email=user["email"])

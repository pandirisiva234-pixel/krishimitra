"""Registration, login, profile and password management."""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AuthError, ConflictError
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    MessageResponse,
    ProfileUpdate,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.language_service import get_language

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _token_response(user: User) -> TokenResponse:
    token = create_access_token(str(user.id), user.role)
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """Create a farmer account and log them in. Admins are created with scripts/create_admin.py."""
    if db.scalars(select(User).where(User.phone == body.phone)).first():
        raise ConflictError("This mobile number is already registered")
    if body.email and db.scalars(select(User).where(User.email == body.email.lower())).first():
        raise ConflictError("This email is already registered")
    language = get_language(db, body.preferred_language)
    user = User(
        full_name=body.full_name,
        phone=body.phone,
        email=body.email.lower() if body.email else None,
        password_hash=hash_password(body.password),
        preferred_language_id=language.id,
        state=body.state,
        district=body.district,
        village=body.village,
        primary_crops=body.primary_crops,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Log in with mobile number (or email) as `username`, and password. Returns a JWT."""
    identifier = form.username.strip().lower()
    digits = re.sub(r"\D", "", identifier)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    user = db.scalars(
        select(User).where(or_(User.phone == (digits or identifier), User.email == identifier))
    ).first()
    # Same message for "no such user" and "wrong password", so accounts cannot be discovered
    if not user or not verify_password(form.password, user.password_hash):
        raise AuthError("Incorrect mobile number/email or password")
    if not user.is_active:
        raise AuthError("This account has been disabled. Contact the administrator.")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return _token_response(user)


@router.post("/logout", response_model=MessageResponse)
def logout(user: User = Depends(get_current_user)):
    """JWTs are stateless: the client deletes its token. The token expires on its own."""
    return MessageResponse(message="Logged out")


@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.put("/profile", response_model=UserOut)
def update_profile(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "preferred_language" in data:
        user.preferred_language_id = get_language(db, data.pop("preferred_language")).id
    if "email" in data and data["email"]:
        email = data["email"].lower()
        clash = db.scalars(select(User).where(User.email == email, User.id != user.id)).first()
        if clash:
            raise ConflictError("This email is already used by another account")
        data["email"] = email
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", response_model=MessageResponse)
def change_password(body: ChangePasswordRequest, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise AuthError("Current password is incorrect", code="wrong_password", status_code=400)
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return MessageResponse(message="Password changed")

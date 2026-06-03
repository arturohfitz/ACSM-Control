from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserMe
from app.services.auth_service import authenticate_user, issue_token
from app.services.login_rate_limit import (
    assert_login_allowed,
    register_login_failure,
    register_login_success,
)
from app.services.permissions import get_user_permission_codes


router = APIRouter()


@router.post("/login", response_model=Token)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    client_host = request.client.host if request.client else "unknown"
    login_key = f"{client_host}:{payload.email.lower()}"
    assert_login_allowed(login_key)
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        register_login_failure(login_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
        )
    register_login_success(login_key)
    return Token(access_token=issue_token(user))


@router.get("/me", response_model=UserMe)
def me(current_user: User = Depends(get_current_user)) -> UserMe:
    data = UserMe.model_validate(current_user)
    data.permissions = sorted(get_user_permission_codes(current_user))
    return data

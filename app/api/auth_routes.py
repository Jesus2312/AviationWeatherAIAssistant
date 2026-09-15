"""Login endpoint issuing JWTs for the demo's single hardcoded user."""

from fastapi import APIRouter, HTTPException, status

from app.auth import authenticate_user, create_access_token
from app.schemas import LoginRequest, TokenResponse

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Log in and obtain a JWT access token",
    responses={401: {"description": "Invalid username or password."}},
)
async def login(request: LoginRequest) -> TokenResponse:
    if not authenticate_user(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(subject=request.username)
    return TokenResponse(access_token=token)

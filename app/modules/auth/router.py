import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.notifications import NotificationService, get_notification_service
from app.core.rate_limit import RateLimiterDep, rate_limit_by_ip
from app.core.security import SecurityService
from app.modules.auth.dependencies import get_security_service, get_user_service, rate_limit_verify_by_email
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    VerifyRequest,
)
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService


def get_auth_service(
    users: Annotated[UserService, Depends(get_user_service)],
    security: Annotated[SecurityService, Depends(get_security_service)],
    notifications: Annotated[NotificationService, Depends(get_notification_service)],
    rate_limiter: RateLimiterDep,
) -> AuthService:
    return AuthService(
        user_service=users,
        security_service=security,
        notification_service=notifications,
        rate_limiter=rate_limiter,
        verification_code_ttl=datetime.timedelta(minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES),
        max_login_failures=settings.MAX_LOGIN_FAILURES,
        login_lockout=datetime.timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES),
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


class AuthController:
    """Groups /auth/* handlers. Bound methods keep FastAPI's DI resolution (self is curried away by Python)."""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/auth", tags=["auth"])
        self.router.add_api_route(
            "/signup",
            self.signup,
            methods=["POST"],
            response_model=UserRead,
            status_code=201,
            summary="Register a new account",
            description="Creates an unverified account and sends a verification code to the email.",
            dependencies=[Depends(rate_limit_by_ip("signup", limit=5, window_seconds=60))],
        )
        self.router.add_api_route(
            "/login",
            self.login,
            methods=["POST"],
            response_model=TokenResponse,
            summary="Log in with email and password",
            # Loose backstop against request floods; the tighter, per-account
            # defense against actual password brute force is the lockout in
            # AuthService.login (MAX_LOGIN_FAILURES / LOGIN_LOCKOUT_MINUTES).
            dependencies=[Depends(rate_limit_by_ip("login", limit=10, window_seconds=60))],
        )
        self.router.add_api_route(
            "/refresh", self.refresh, methods=["POST"], response_model=TokenResponse, summary="Refresh an access token"
        )
        self.router.add_api_route(
            "/verify",
            self.verify,
            methods=["POST"],
            response_model=UserRead,
            summary="Verify an email address",
            dependencies=[Depends(rate_limit_verify_by_email(limit=5, window_seconds=300))],
        )

    async def signup(self, payload: SignupRequest, auth_service: AuthServiceDep) -> UserRead:
        user = await auth_service.signup(
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        return UserRead.model_validate(user)

    async def login(self, payload: LoginRequest, auth_service: AuthServiceDep) -> TokenResponse:
        return await auth_service.login(payload.email, payload.password)

    async def refresh(self, payload: RefreshRequest, auth_service: AuthServiceDep) -> TokenResponse:
        return await auth_service.refresh(payload.refresh_token)

    async def verify(self, payload: VerifyRequest, auth_service: AuthServiceDep) -> UserRead:
        user = await auth_service.verify_email(payload.email, payload.code)
        return UserRead.model_validate(user)


router = AuthController().router

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.core.exceptions import ForbiddenError
from app.core.pagination import Page, PaginationDep
from app.modules.auth.dependencies import require_role
from app.modules.users.models import Role, User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import RoleUpdate, UserRead, UserUpdate
from app.modules.users.service import UserService


def get_user_service(db: DbSession) -> UserService:
    return UserService(UserRepository(db))


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


class UsersController:
    """Groups /me and /users/* handlers."""

    def __init__(self) -> None:
        self.router = APIRouter(tags=["users"])
        self.router.add_api_route(
            "/me", self.get_me, methods=["GET"], response_model=UserRead, summary="Get the current user's profile"
        )
        self.router.add_api_route(
            "/users", self.list_users, methods=["GET"], response_model=Page[UserRead], summary="List users (admin only)"
        )
        self.router.add_api_route(
            "/users/{user_id}",
            self.get_user,
            methods=["GET"],
            response_model=UserRead,
            summary="Get a user by id (admin only)",
        )
        self.router.add_api_route(
            "/users/{user_id}",
            self.update_user,
            methods=["PATCH"],
            response_model=UserRead,
            summary="Update a user's profile",
            description="Self or admin only. Updates first/last name.",
        )
        self.router.add_api_route(
            "/users/{user_id}/role",
            self.update_role,
            methods=["PATCH"],
            response_model=UserRead,
            summary="Change a user's role (admin only)",
            description="Admins cannot change their own role.",
        )
        self.router.add_api_route(
            "/users/{user_id}", self.delete_user, methods=["DELETE"], status_code=204, summary="Delete a user (admin only)"
        )

    async def get_me(self, current_user: Annotated[User, Depends(require_role())]) -> UserRead:
        return UserRead.model_validate(current_user)

    async def list_users(
        self,
        service: UserServiceDep,
        _admin: Annotated[User, Depends(require_role(Role.ADMIN))],
        pagination: PaginationDep,
    ) -> Page[UserRead]:
        users, total = await service.list_users(offset=pagination.offset, limit=pagination.page_size)
        return Page.build([UserRead.model_validate(user) for user in users], total, pagination)

    async def get_user(
        self,
        user_id: int,
        service: UserServiceDep,
        _admin: Annotated[User, Depends(require_role(Role.ADMIN))],
    ) -> UserRead:
        user = await service.get_by_id(user_id)
        return UserRead.model_validate(user)

    async def update_user(
        self,
        user_id: int,
        payload: UserUpdate,
        service: UserServiceDep,
        current_user: Annotated[User, Depends(require_role())],
    ) -> UserRead:
        if current_user.role != Role.ADMIN and current_user.id != user_id:
            raise ForbiddenError("You can only update your own profile")

        user = await service.update_user(user_id, payload)
        return UserRead.model_validate(user)

    async def update_role(
        self,
        user_id: int,
        payload: RoleUpdate,
        service: UserServiceDep,
        current_admin: Annotated[User, Depends(require_role(Role.ADMIN))],
    ) -> UserRead:
        user = await service.update_role(user_id, payload.role, requested_by=current_admin.id)
        return UserRead.model_validate(user)

    async def delete_user(
        self,
        user_id: int,
        service: UserServiceDep,
        _admin: Annotated[User, Depends(require_role(Role.ADMIN))],
    ) -> None:
        await service.delete_user(user_id)


router = UsersController().router

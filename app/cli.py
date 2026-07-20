import argparse
import asyncio
import getpass

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.security import SecurityService
from app.modules.users.models import Role
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService


async def create_admin(email: str, password: str, first_name: str | None, last_name: str | None) -> None:
    async with async_session_factory() as session:
        service = UserService(UserRepository(session))
        security = SecurityService(settings)

        existing = await service.get_by_email(email)
        if existing is not None:
            user = await service.set_role(existing.id, Role.ADMIN)
            await service.verify_user(user)
            await session.commit()
            print(f"Promoted existing user '{email}' (id={user.id}) to admin.")
            return

        password_hash = security.hash_password(password)
        user = await service.register_user(
            UserCreate(email=email, password_hash=password_hash, first_name=first_name, last_name=last_name)
        )
        user = await service.set_role(user.id, Role.ADMIN)
        await service.verify_user(user)
        await session.commit()
        print(f"Created admin user '{email}' (id={user.id}).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin account, or promote an existing user to admin.")
    parser.add_argument("email")
    parser.add_argument("--password", help="Prompted securely if omitted (avoids landing in shell history)")
    parser.add_argument("--first-name", default=None)
    parser.add_argument("--last-name", default=None)
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        parser.error("password must be at least 8 characters")

    asyncio.run(create_admin(args.email, password, args.first_name, args.last_name))


if __name__ == "__main__":
    main()

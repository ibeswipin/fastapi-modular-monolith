from abc import ABC, abstractmethod


class NotificationService(ABC):
    @abstractmethod
    async def send_verification_code(self, email: str, code: str) -> None:
        raise NotImplementedError


class ConsoleNotificationService(NotificationService):
    """Dev implementation — prints instead of sending."""

    async def send_verification_code(self, email: str, code: str) -> None:
        print(f"[notifications] verification code for {email}: {code}")

    # ponytail: no production impl (SMTP/SES/Twilio) yet — no real provider/
    # credentials to wire up. Same interface, new class, when that exists.


def get_notification_service() -> NotificationService:
    return ConsoleNotificationService()

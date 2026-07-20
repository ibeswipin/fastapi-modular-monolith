class AppError(Exception):
    pass


class NotFoundError(AppError):
    pass


class ConflictError(AppError):
    pass


class UnauthorizedError(AppError):
    pass


class ForbiddenError(AppError):
    pass


class RateLimitExceededError(AppError):
    pass


class AccountLockedError(AppError):
    pass


# users module
class UserNotFoundError(NotFoundError):
    pass


class EmailAlreadyExistsError(ConflictError):
    pass


# auth module
class InvalidCredentialsError(UnauthorizedError):
    pass


class InvalidTokenError(UnauthorizedError):
    pass


class UserNotVerifiedError(ForbiddenError):
    pass


class InvalidVerificationCodeError(UnauthorizedError):
    pass


class AlreadyVerifiedError(ConflictError):
    pass

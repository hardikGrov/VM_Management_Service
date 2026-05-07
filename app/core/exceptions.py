from http import HTTPStatus


class AppError(Exception):
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class VMNotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "vm_not_found"


class VMConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = "vm_conflict"


class VMProviderError(AppError):
    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "vm_provider_error"


class VMOperationError(AppError):
    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "vm_operation_error"


class VMInvalidStateError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = "vm_invalid_state"

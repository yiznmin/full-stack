class AppError(Exception):
    def __init__(self, status_code: int, detail: str, code: str | None = None):
        self.status_code = status_code
        self.detail = detail
        self.code = code


class BadRequestError(AppError):
    def __init__(self, detail: str = "請求無法處理", code: str | None = None):
        super().__init__(400, detail, code)


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "請先登入", code: str | None = None):
        super().__init__(401, detail, code)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "權限不足", code: str | None = None):
        super().__init__(403, detail, code)


class NotFoundError(AppError):
    def __init__(self, detail: str = "資源不存在", code: str | None = None):
        super().__init__(404, detail, code)


class ConflictError(AppError):
    def __init__(self, detail: str = "資料衝突", code: str | None = None):
        super().__init__(409, detail, code)


class GoneError(AppError):
    def __init__(self, detail: str = "資源已過期", code: str | None = None):
        super().__init__(410, detail, code)


class ExternalServiceError(AppError):
    def __init__(self, detail: str = "外部服務異常，請稍後再試", code: str | None = None):
        super().__init__(503, detail, code)

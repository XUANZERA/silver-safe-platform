from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.headers = headers
        super().__init__(message)


def _error_response(
    status_code: int,
    message: str,
    error_code: str,
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": error_code,
                "message": message,
            },
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            exc.status_code,
            exc.message,
            exc.error_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        location = tuple(first_error.get("loc", ()))
        field = ".".join(str(part) for part in location[1:])
        detail = first_error.get("msg", "字段格式错误")
        message = f"字段 {field}：{detail}" if field else detail

        if field in {"latitude", "longitude"}:
            return _error_response(400, "经纬度不合法", "INVALID_COORDINATES")
        if location[:2] == ("query", "limit"):
            return _error_response(400, "limit 必须在 1 到 500 之间", "INVALID_LIMIT")
        return _error_response(422, message, "VALIDATION_ERROR")

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        codes = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
        }
        return _error_response(
            exc.status_code,
            str(exc.detail),
            codes.get(exc.status_code, "HTTP_ERROR"),
        )

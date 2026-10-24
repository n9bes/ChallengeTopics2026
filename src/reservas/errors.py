"""Codigos de error y normalizacion de las respuestas 4xx.

Corresponde a las secciones 7.2 y 7.4 de `docs/spec.md` y a la decision D-006.

`ApiError` es el unico tipo de error que usan todas las capas: lleva un codigo estable
del contrato y el estado HTTP se deriva de ese codigo. La contrapartida es que la capa
de persistencia conoce los codigos del contrato; se acepta para no mantener una tabla
de traduccion paralela en una aplicacion de este tamano.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from reservas.models import Error, ErrorBody


class ErrorCode(str, Enum):
    """Codigos estables de error (seccion 7.4)."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNKNOWN_UNIT = "UNKNOWN_UNIT"
    INVALID_REQUESTER = "INVALID_REQUESTER"
    INVALID_INTERVAL = "INVALID_INTERVAL"
    START_IN_PAST = "START_IN_PAST"
    TOO_FAR_AHEAD = "TOO_FAR_AHEAD"
    DURATION_TOO_LONG = "DURATION_TOO_LONG"
    OVERLAP = "OVERLAP"
    ALREADY_CANCELLED = "ALREADY_CANCELLED"
    UNIT_NOT_FOUND = "UNIT_NOT_FOUND"
    RESERVATION_NOT_FOUND = "RESERVATION_NOT_FOUND"


STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.UNKNOWN_UNIT: 422,
    ErrorCode.INVALID_REQUESTER: 422,
    ErrorCode.INVALID_INTERVAL: 422,
    ErrorCode.START_IN_PAST: 422,
    ErrorCode.TOO_FAR_AHEAD: 422,
    ErrorCode.DURATION_TOO_LONG: 422,
    ErrorCode.OVERLAP: 409,
    ErrorCode.ALREADY_CANCELLED: 409,
    ErrorCode.UNIT_NOT_FOUND: 404,
    ErrorCode.RESERVATION_NOT_FOUND: 404,
}
"""Estado HTTP de cada codigo, segun la tabla de la seccion 7.4."""


class ApiError(Exception):
    """Rechazo con un codigo del contrato.

    Entradas: `code` de la seccion 7.4, `message` legible en espanol y `details`
    opcional. Salida: una respuesta 4xx con el sobre `Error`.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: list[dict[str, Any]] = details or []

    @property
    def status_code(self) -> int:
        return STATUS_BY_CODE[self.code]


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Construye la respuesta de error con el sobre unico del contrato."""
    body = Error(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Normaliza los errores de Pydantic a `loc`, `msg` y `type` por campo."""
    return [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        }
        for error in exc.errors()
    ]


def register_error_handlers(app: FastAPI) -> None:
    """Deja toda respuesta 4xx con la forma `{"error": {...}}` (D-006)."""

    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(
            status_code=exc.status_code,
            code=exc.code.value,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            status_code=STATUS_BY_CODE[ErrorCode.VALIDATION_ERROR],
            code=ErrorCode.VALIDATION_ERROR.value,
            message="La solicitud tiene campos inválidos o faltantes.",
            details=validation_details(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Cubre los errores que genera el router, como una ruta o un metodo invalidos."""
        generic_codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        code = generic_codes.get(exc.status_code, "HTTP_ERROR")
        return error_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
        )

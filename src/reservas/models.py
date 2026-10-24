"""Modelos del contrato de la API.

Corresponden a la seccion 7.2 de `docs/spec.md`.

Invariantes:

- Las entradas de fecha y hora usan `AwareDatetime`: una hora sin offset se rechaza
  con `VALIDATION_ERROR` (S-01).
- Toda fecha serializada a JSON sale normalizada a UTC con sufijo `Z` (S-02).
- `ReservationCreate` acepta `unit_id` y `requester` como texto libre a proposito: el
  rechazo de una unidad desconocida o de un solicitante vacio corresponde a los codigos
  `UNKNOWN_UNIT` e `INVALID_REQUESTER`, no a `VALIDATION_ERROR` (seccion 7.4).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, PlainSerializer

ReservationStatus = Literal["active", "cancelled"]
"""Estados posibles de una reserva (R-08)."""


def format_utc(value: datetime) -> str:
    """Devuelve el instante en UTC con sufijo `Z`, sin redondear (S-02, S-05)."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[
    AwareDatetime,
    PlainSerializer(format_utc, return_type=str, when_used="json"),
]
"""Fecha y hora con offset obligatorio a la entrada y UTC con `Z` a la salida."""


class Unit(BaseModel):
    """Unidad fisica del inventario (seccion 3)."""

    id: str
    name: str


class ReservationCreate(BaseModel):
    """Cuerpo de entrada de `POST /reservations`. Los campos extra se ignoran."""

    unit_id: str
    requester: str
    start: UtcDatetime
    end: UtcDatetime


class Reservation(BaseModel):
    """Reserva tal como la devuelve la API."""

    id: int
    unit_id: str
    requester: str
    start: UtcDatetime
    end: UtcDatetime
    status: ReservationStatus
    created_at: UtcDatetime
    cancelled_at: UtcDatetime | None = None


class Availability(BaseModel):
    """Respuesta de `GET /units/{unit_id}/availability`."""

    unit_id: str
    start: UtcDatetime
    end: UtcDatetime
    available: bool
    conflicts: list[Reservation] = Field(default_factory=list)


class ErrorBody(BaseModel):
    """Contenido del sobre de error.

    `details` es una lista de objetos cuya forma depende del codigo: en
    `VALIDATION_ERROR` lleva `loc`, `msg` y `type` por campo invalido; en `OVERLAP`
    lleva las reservas en conflicto.
    """

    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class Error(BaseModel):
    """Sobre unico de toda respuesta 4xx (D-006)."""

    error: ErrorBody

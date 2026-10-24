"""Reglas de negocio y validaciones.

Corresponde a las secciones 4 y 5 de `docs/spec.md`.

Invariantes:

- `intervals_overlap` es la unica implementacion de la regla de superposicion (R-03).
  La creacion de reservas y la consulta de disponibilidad la usan sin duplicarla, que
  es lo que garantiza R-07.
- Los intervalos son semiabiertos `[inicio, fin)`: 10:00-11:00 y 11:00-12:00 no se
  superponen (R-02).
- Las validaciones de ventana (V-05 a V-07) aplican solo al crear, nunca a la consulta
  de disponibilidad (S-04).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from reservas.errors import ApiError, ErrorCode

MAX_SPAN = timedelta(days=30)
"""Duracion y anticipacion maximas: 30 x 24 horas exactas (S-04, D-007)."""

REQUESTER_MAX_LENGTH = 100
"""Cota maxima del solicitante ya recortado (V-02, S-06)."""


def intervals_overlap(
    first_start: datetime,
    first_end: datetime,
    second_start: datetime,
    second_end: datetime,
) -> bool:
    """Indica si dos intervalos semiabiertos se superponen (R-03).

    Entradas: los extremos de dos intervalos, comparables entre si. Salida: `True` si
    y solo si `first_start < second_end and second_start < first_end`.

    Unica fuente de la regla. No reimplementar esta comparacion en SQL ni en la capa
    HTTP: R-07 exige que la consulta de disponibilidad y la creacion decidan igual.
    """
    return first_start < second_end and second_start < first_end


def normalize_requester(raw: str) -> str:
    """Recorta el solicitante y valida V-02.

    Entrada: el texto tal como llego. Salida: el texto sin espacios al inicio ni al
    final, que es la forma en que se guarda (S-06).

    Rechaza con `INVALID_REQUESTER` si queda vacio o supera los 100 caracteres.
    """
    requester = raw.strip()
    if not requester:
        raise ApiError(
            ErrorCode.INVALID_REQUESTER,
            "El solicitante no puede estar vacío ni contener solo espacios.",
        )
    if len(requester) > REQUESTER_MAX_LENGTH:
        raise ApiError(
            ErrorCode.INVALID_REQUESTER,
            f"El solicitante no puede superar los {REQUESTER_MAX_LENGTH} caracteres.",
        )
    return requester


def ensure_valid_interval(start: datetime, end: datetime) -> None:
    """Valida V-04: el inicio es estrictamente anterior al fin."""
    if start >= end:
        raise ApiError(
            ErrorCode.INVALID_INTERVAL,
            "El inicio debe ser estrictamente anterior al fin.",
        )


def ensure_within_booking_window(start: datetime, end: datetime, now: datetime) -> None:
    """Valida V-05, V-06 y V-07 en el orden que fija la seccion 7.4.

    Entradas: extremos de la reserva y momento actual, todos con zona horaria. Los
    limites exactos se aceptan: inicio igual al ahora, anticipacion de 30 dias justos
    y duracion de 30 dias justos son validos (CA-20, CA-31, CA-33).
    """
    if start < now:
        raise ApiError(
            ErrorCode.START_IN_PAST,
            "El inicio no puede ser anterior al momento actual.",
        )
    if start > now + MAX_SPAN:
        raise ApiError(
            ErrorCode.TOO_FAR_AHEAD,
            f"El inicio no puede superar los {MAX_SPAN.days} días de anticipación.",
        )
    if end - start > MAX_SPAN:
        raise ApiError(
            ErrorCode.DURATION_TOO_LONG,
            f"La duración no puede superar los {MAX_SPAN.days} días.",
        )

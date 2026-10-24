"""Fabrica de la aplicacion y endpoints HTTP.

Corresponde a las secciones 7.1 y 7.3 de `docs/spec.md`.

Invariantes:

- `create_app` recibe la base y el reloj por parametro (D-006, S-08). Dos aplicaciones
  sobre el mismo archivo equivalen a reiniciar el servidor.
- El orden de evaluacion al crear es el de la seccion 7.4: `VALIDATION_ERROR`,
  `UNKNOWN_UNIT`, `INVALID_REQUESTER`, `INVALID_INTERVAL`, `START_IN_PAST`,
  `TOO_FAR_AHEAD`, `DURATION_TOO_LONG`, `OVERLAP`.
- La disponibilidad y la creacion comparten la misma busqueda de conflictos
  (`Database.find_conflicts`), que usa `domain.intervals_overlap` (R-07).

Este modulo no usa `from __future__ import annotations` a proposito: las dependencias
(`require_unit`, `require_reservation`) son funciones locales de `create_app`, y con
anotaciones diferidas FastAPI no puede resolver `Depends(...)` contra los nombres
globales del modulo.
"""

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Path as PathParam, Query
from pydantic import AwareDatetime

from reservas import __version__
from reservas.domain import (
    ensure_valid_interval,
    ensure_within_booking_window,
    normalize_requester,
)
from reservas.errors import ApiError, ErrorCode, register_error_handlers
from reservas.models import (
    Availability,
    Error,
    Reservation,
    ReservationCreate,
    ReservationStatus,
    Unit,
)
from reservas.storage import Database, load_inventory

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    404: {"model": Error},
    409: {"model": Error},
    422: {"model": Error},
}
"""Documenta en OpenAPI que todo 4xx usa el sobre `Error` (D-006)."""


def create_app(*, db_path: Path, clock: Callable[[], datetime]) -> FastAPI:
    """Construye la aplicacion sobre un archivo SQLite y un reloj inyectado.

    Entradas:

    - `db_path`: archivo SQLite. Se crea con el esquema y el inventario si no existe.
    - `clock`: devuelve el momento actual como `datetime` con zona horaria.

    Salida: la aplicacion FastAPI con los seis endpoints del contrato.
    """
    database = Database(Path(db_path))
    database.initialize(load_inventory())

    app = FastAPI(
        title="Sistema de reservas del laboratorio",
        version=__version__,
        description="Implementa el contrato congelado de docs/spec.md v1.0.0.",
    )
    register_error_handlers(app)

    def now() -> datetime:
        """Momento actual en UTC (S-02, S-08)."""
        current = clock()
        if current.tzinfo is None or current.tzinfo.utcoffset(current) is None:
            raise RuntimeError(
                "El reloj inyectado debe devolver un datetime con zona horaria."
            )
        return current.astimezone(timezone.utc)

    def require_unit(
        unit_id: Annotated[str, PathParam(description="ID exacto de la unidad")],
    ) -> Unit:
        """Resuelve la unidad de la ruta o rechaza con `UNIT_NOT_FOUND`."""
        unit = database.get_unit(unit_id)
        if unit is None:
            raise ApiError(
                ErrorCode.UNIT_NOT_FOUND,
                f"No existe la unidad {unit_id} en el inventario.",
            )
        return unit

    def require_reservation(
        reservation_id: Annotated[int, PathParam(description="ID de la reserva")],
    ) -> Reservation:
        """Resuelve la reserva de la ruta o rechaza con `RESERVATION_NOT_FOUND`."""
        reservation = database.get_reservation(reservation_id)
        if reservation is None:
            raise ApiError(
                ErrorCode.RESERVATION_NOT_FOUND,
                f"No existe la reserva {reservation_id}.",
            )
        return reservation

    @app.get("/units", response_model=list[Unit], summary="Inventario completo")
    def get_units() -> list[Unit]:
        return database.list_units()

    @app.get(
        "/units/{unit_id}/availability",
        response_model=Availability,
        responses=ERROR_RESPONSES,
        summary="Disponibilidad de una unidad en un intervalo",
    )
    def get_availability(
        unit: Annotated[Unit, Depends(require_unit)],
        start: Annotated[AwareDatetime, Query(description="Inicio, ISO 8601 con offset")],
        end: Annotated[AwareDatetime, Query(description="Fin, ISO 8601 con offset")],
    ) -> Availability:
        """La consulta acepta cualquier rango valido: V-05 a V-07 no aplican (S-04)."""
        ensure_valid_interval(start, end)
        conflicts = database.find_conflicts(unit.id, start, end)
        return Availability(
            unit_id=unit.id,
            start=start,
            end=end,
            available=not conflicts,
            conflicts=conflicts,
        )

    @app.post(
        "/reservations",
        response_model=Reservation,
        status_code=201,
        responses=ERROR_RESPONSES,
        summary="Crear reserva",
    )
    def post_reservation(payload: ReservationCreate) -> Reservation:
        unit = database.get_unit(payload.unit_id)
        if unit is None:
            raise ApiError(
                ErrorCode.UNKNOWN_UNIT,
                f"La unidad {payload.unit_id} no existe en el inventario.",
            )
        requester = normalize_requester(payload.requester)
        ensure_valid_interval(payload.start, payload.end)
        current = now()
        ensure_within_booking_window(payload.start, payload.end, current)
        return database.create_reservation(
            unit_id=unit.id,
            requester=requester,
            start=payload.start,
            end=payload.end,
            created_at=current,
        )

    @app.get(
        "/reservations",
        response_model=list[Reservation],
        responses=ERROR_RESPONSES,
        summary="Historial de reservas",
    )
    def get_reservations(
        unit_id: Annotated[str | None, Query(description="Filtro por unidad")] = None,
        status: Annotated[
            ReservationStatus | None, Query(description="Filtro por estado")
        ] = None,
    ) -> list[Reservation]:
        if unit_id is not None and database.get_unit(unit_id) is None:
            raise ApiError(
                ErrorCode.UNKNOWN_UNIT,
                f"La unidad {unit_id} no existe en el inventario.",
            )
        return database.list_reservations(unit_id=unit_id, status=status)

    @app.get(
        "/reservations/{reservation_id}",
        response_model=Reservation,
        responses=ERROR_RESPONSES,
        summary="Una reserva",
    )
    def get_reservation(
        reservation: Annotated[Reservation, Depends(require_reservation)],
    ) -> Reservation:
        return reservation

    @app.post(
        "/reservations/{reservation_id}/cancel",
        response_model=Reservation,
        responses=ERROR_RESPONSES,
        summary="Cancelar una reserva",
    )
    def cancel_reservation(
        reservation: Annotated[Reservation, Depends(require_reservation)],
    ) -> Reservation:
        """Cancelar conserva la fila; nunca borra (R-08)."""
        return database.cancel_reservation(reservation.id, now())

    return app

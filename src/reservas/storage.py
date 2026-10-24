"""Persistencia SQLite.

Corresponde a la seccion 8 de `docs/spec.md`.

Invariantes:

- Las fechas se guardan en UTC con el formato fijo `YYYY-MM-DDTHH:MM:SS.ffffffZ`, que
  ordena igual como texto que como tiempo.
- Nunca se borra una fila de `reservations`: cancelar solo cambia `status` y escribe
  `cancelled_at` (R-08).
- La verificacion de superposicion y la insercion ocurren en la misma transaccion de
  escritura, abierta con `BEGIN IMMEDIATE` (S-09).
- Los conflictos se deciden en Python con `domain.intervals_overlap`, no con una
  comparacion escrita de nuevo en SQL (R-07). SQL solo filtra las candidatas: las
  reservas activas de la unidad. Para un laboratorio local el costo es irrelevante y
  el beneficio es que existe una sola definicion de "se superponen".
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from reservas.domain import intervals_overlap
from reservas.errors import ApiError, ErrorCode
from reservas.models import Reservation, ReservationStatus, Unit, format_utc

INVENTORY_PATH = Path(__file__).with_name("inventory.json")
"""Inventario precargado (seccion 3)."""

DB_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
"""Formato fijo de las fechas en la base, sin el sufijo Z."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id      TEXT NOT NULL REFERENCES units (id),
    requester    TEXT NOT NULL,
    start_at     TEXT NOT NULL,
    end_at       TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('active', 'cancelled')),
    created_at   TEXT NOT NULL,
    cancelled_at TEXT,
    CHECK (start_at < end_at),
    CHECK (length(requester) BETWEEN 1 AND 100),
    CHECK ((status = 'cancelled') = (cancelled_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS reservations_unit_status
    ON reservations (unit_id, status);
"""

RESERVATION_COLUMNS = (
    "id, unit_id, requester, start_at, end_at, status, created_at, cancelled_at"
)

SELECT_RESERVATION = f"SELECT {RESERVATION_COLUMNS} FROM reservations"


def to_db_text(value: datetime) -> str:
    """Convierte un instante con zona horaria al texto UTC que guarda la base."""
    return value.astimezone(timezone.utc).strftime(DB_TIMESTAMP_FORMAT) + "Z"


def from_db_text(value: str) -> datetime:
    """Lee el texto de la base como `datetime` en UTC."""
    return datetime.strptime(value, DB_TIMESTAMP_FORMAT + "Z").replace(
        tzinfo=timezone.utc
    )


def load_inventory(path: Path = INVENTORY_PATH) -> list[Unit]:
    """Lee y valida el inventario del archivo JSON."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Unit.model_validate(item) for item in raw]


def _to_reservation(row: sqlite3.Row) -> Reservation:
    cancelled_at = row["cancelled_at"]
    return Reservation(
        id=row["id"],
        unit_id=row["unit_id"],
        requester=row["requester"],
        start=from_db_text(row["start_at"]),
        end=from_db_text(row["end_at"]),
        status=row["status"],
        created_at=from_db_text(row["created_at"]),
        cancelled_at=from_db_text(cancelled_at) if cancelled_at else None,
    )


class Database:
    """Acceso a la base SQLite de un archivo.

    Abre una conexion por operacion: los endpoints sincronos de FastAPI corren en
    hilos distintos y una conexion de sqlite3 no se comparte entre hilos.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    # -- conexiones --------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, isolation_level=None, timeout=10.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _write_transaction(self) -> Iterator[sqlite3.Connection]:
        """Transaccion de escritura exclusiva (S-09)."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            connection.commit()

    # -- esquema e inventario ----------------------------------------------

    def initialize(self, units: Sequence[Unit]) -> None:
        """Crea el archivo, el esquema y carga el inventario sin duplicarlo.

        `executescript` va fuera de la transaccion explicita porque sqlite3 confirma
        cualquier transaccion pendiente antes de ejecutar un script.
        """
        parent = self._path.parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
        with self._write_transaction() as connection:
            connection.executemany(
                "INSERT INTO units (id, name) VALUES (?, ?)"
                " ON CONFLICT (id) DO UPDATE SET name = excluded.name",
                [(unit.id, unit.name) for unit in units],
            )

    # -- consultas ---------------------------------------------------------

    def list_units(self) -> list[Unit]:
        """Inventario completo ordenado por ID."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name FROM units ORDER BY id"
            ).fetchall()
        return [Unit(id=row["id"], name=row["name"]) for row in rows]

    def get_unit(self, unit_id: str) -> Unit | None:
        """Busca una unidad con comparacion exacta, sensible a mayusculas (V-01)."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name FROM units WHERE id = ?", (unit_id,)
            ).fetchone()
        return Unit(id=row["id"], name=row["name"]) if row else None

    def get_reservation(self, reservation_id: int) -> Reservation | None:
        with self._connect() as connection:
            row = connection.execute(
                f"{SELECT_RESERVATION} WHERE id = ?", (reservation_id,)
            ).fetchone()
        return _to_reservation(row) if row else None

    def list_reservations(
        self,
        *,
        unit_id: str | None = None,
        status: ReservationStatus | None = None,
    ) -> list[Reservation]:
        """Historial con filtros opcionales, ordenado por inicio y luego por ID."""
        conditions: list[str] = []
        parameters: list[object] = []
        if unit_id is not None:
            conditions.append("unit_id = ?")
            parameters.append(unit_id)
        if status is not None:
            conditions.append("status = ?")
            parameters.append(status)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"{SELECT_RESERVATION}{where} ORDER BY start_at, id", parameters
            ).fetchall()
        return [_to_reservation(row) for row in rows]

    def find_conflicts(
        self, unit_id: str, start: datetime, end: datetime
    ) -> list[Reservation]:
        """Reservas activas de la unidad que se superponen, ordenadas por inicio."""
        with self._connect() as connection:
            return self._conflicts(connection, unit_id, start, end)

    def _conflicts(
        self,
        connection: sqlite3.Connection,
        unit_id: str,
        start: datetime,
        end: datetime,
    ) -> list[Reservation]:
        rows = connection.execute(
            f"{SELECT_RESERVATION} WHERE unit_id = ? AND status = 'active'"
            " ORDER BY start_at, id",
            (unit_id,),
        ).fetchall()
        return [
            reservation
            for reservation in (_to_reservation(row) for row in rows)
            if intervals_overlap(reservation.start, reservation.end, start, end)
        ]

    # -- escrituras --------------------------------------------------------

    def create_reservation(
        self,
        *,
        unit_id: str,
        requester: str,
        start: datetime,
        end: datetime,
        created_at: datetime,
    ) -> Reservation:
        """Crea una reserva activa si no se superpone con otra activa (R-05, S-09).

        Rechaza con `OVERLAP` y lista las reservas en conflicto en `details`.
        """
        with self._write_transaction() as connection:
            conflicts = self._conflicts(connection, unit_id, start, end)
            if conflicts:
                raise ApiError(
                    ErrorCode.OVERLAP,
                    f"La unidad {unit_id} ya tiene una reserva activa en ese intervalo.",
                    details=[
                        {
                            "reservation_id": conflict.id,
                            "start": format_utc(conflict.start),
                            "end": format_utc(conflict.end),
                        }
                        for conflict in conflicts
                    ],
                )
            cursor = connection.execute(
                "INSERT INTO reservations"
                " (unit_id, requester, start_at, end_at, status, created_at, cancelled_at)"
                " VALUES (?, ?, ?, ?, 'active', ?, NULL)",
                (
                    unit_id,
                    requester,
                    to_db_text(start),
                    to_db_text(end),
                    to_db_text(created_at),
                ),
            )
            row = connection.execute(
                f"{SELECT_RESERVATION} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return _to_reservation(row)

    def cancel_reservation(
        self, reservation_id: int, cancelled_at: datetime
    ) -> Reservation:
        """Cancela una reserva activa conservando la fila (R-08, R-09).

        Rechaza con `RESERVATION_NOT_FOUND` si el ID no existe y con
        `ALREADY_CANCELLED` si ya estaba cancelada.
        """
        with self._write_transaction() as connection:
            row = connection.execute(
                f"{SELECT_RESERVATION} WHERE id = ?", (reservation_id,)
            ).fetchone()
            if row is None:
                raise ApiError(
                    ErrorCode.RESERVATION_NOT_FOUND,
                    f"No existe la reserva {reservation_id}.",
                )
            if row["status"] == "cancelled":
                raise ApiError(
                    ErrorCode.ALREADY_CANCELLED,
                    f"La reserva {reservation_id} ya estaba cancelada.",
                )
            connection.execute(
                "UPDATE reservations SET status = 'cancelled', cancelled_at = ?"
                " WHERE id = ? AND status = 'active'",
                (to_db_text(cancelled_at), reservation_id),
            )
            updated = connection.execute(
                f"{SELECT_RESERVATION} WHERE id = ?", (reservation_id,)
            ).fetchone()
        return _to_reservation(updated)

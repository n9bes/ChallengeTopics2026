"""Datos y verificaciones compartidas por las pruebas de contrato.

Propósito: traducir a código los valores fijos de la sección 10 de `docs/spec.md`
(reloj de referencia, reserva "base") y las verificaciones que el contrato declara
estables.

No contiene dobles de prueba ni lógica de negocio: todas las pruebas ejercen la
aplicación real construida por `reservas.api.create_app`.

Invariante: nunca se verifica `error.message`; la sección 7.2 lo declara no estable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi.testclient import TestClient

# Reloj de referencia de todos los criterios (sección 10).
CLOCK_NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

# "Base": reserva previa activa de MIC-01 de 10:00 a 11:00 del 2026-11-03 en -03:00.
BASE_UNIT = "MIC-01"
BASE_START = "2026-11-03T10:00:00-03:00"
BASE_END = "2026-11-03T11:00:00-03:00"
BASE_START_UTC = datetime(2026, 11, 3, 13, 0, 0, tzinfo=timezone.utc)
BASE_END_UTC = datetime(2026, 11, 3, 14, 0, 0, tzinfo=timezone.utc)

# Solicitantes ficticios.
REQUESTER_BASE = "Ana Pérez"
REQUESTER_OTRO = "Bruno Salas"
REQUESTER_TERCERO = "Carla Ibáñez"


def crear_reserva(
    client: TestClient,
    *,
    unit_id: str = BASE_UNIT,
    requester: str = REQUESTER_BASE,
    start: str = BASE_START,
    end: str = BASE_END,
) -> httpx.Response:
    """POST /reservations con un cuerpo ReservationCreate completo."""
    return client.post(
        "/reservations",
        json={"unit_id": unit_id, "requester": requester, "start": start, "end": end},
    )


def crear_base(client: TestClient) -> dict[str, Any]:
    """Crea la reserva "base" y la devuelve. Falla si la creación no da 201."""
    response = crear_reserva(client)
    assert response.status_code == 201, response.text
    return response.json()


def crear_base_cancelada(client: TestClient) -> dict[str, Any]:
    """Crea la reserva "base" y la cancela. Devuelve la reserva cancelada."""
    base = crear_base(client)
    response = cancelar(client, base["id"])
    assert response.status_code == 200, response.text
    return response.json()


def cancelar(client: TestClient, reservation_id: int) -> httpx.Response:
    return client.post(f"/reservations/{reservation_id}/cancel")


def consultar_disponibilidad(
    client: TestClient, unit_id: str, start: str, end: str
) -> httpx.Response:
    return client.get(
        f"/units/{unit_id}/availability",
        params={"start": start, "end": end},
    )


def parse_utc(value: str) -> datetime:
    """Valida el formato de salida de S-02 (UTC con sufijo Z) y devuelve el instante."""
    assert isinstance(value, str), f"se esperaba una cadena ISO 8601, se recibio {value!r}"
    assert value.endswith("Z"), f"se esperaba UTC con sufijo Z, se recibio {value!r}"
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assert_error(response: httpx.Response, *, status: int, code: str) -> dict[str, Any]:
    """Verifica el status HTTP y `error.code`, los dos valores estables del contrato."""
    assert response.status_code == status, (
        f"se esperaba HTTP {status} y se recibio {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "error" in body, f"el cuerpo de error no tiene la clave 'error': {body!r}"
    assert body["error"]["code"] == code, (
        f"se esperaba error.code {code!r} y se recibio {body['error'].get('code')!r}"
    )
    return body["error"]

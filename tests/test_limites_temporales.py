"""Límites de fecha, duración y anticipación: CA-19, CA-20, CA-31 a CA-34.

Validaciones cubiertas: V-05 (S-03), V-06 y V-07 (S-04, 30 días fijos, límite exacto
aceptado).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from helpers import assert_error, crear_reserva, parse_utc


def test_ca19_rechaza_inicio_en_el_pasado(client: TestClient) -> None:
    # 08:00-03:00 es 11:00Z, una hora antes del reloj de referencia.
    response = crear_reserva(
        client,
        start="2026-11-02T08:00:00-03:00",
        end="2026-11-02T10:00:00-03:00",
    )

    assert_error(response, status=422, code="START_IN_PAST")


def test_ca20_acepta_inicio_exactamente_en_el_momento_actual(client: TestClient) -> None:
    # S-03: un inicio igual al momento actual se acepta.
    response = crear_reserva(
        client,
        start="2026-11-02T12:00:00Z",
        end="2026-11-02T13:00:00Z",
    )

    assert response.status_code == 201, response.text
    reserva = response.json()
    assert reserva["status"] == "active"
    assert parse_utc(reserva["start"]) == datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def test_ca31_acepta_duracion_de_exactamente_30_dias(client: TestClient) -> None:
    response = crear_reserva(
        client,
        start="2026-11-03T13:00:00Z",
        end="2026-12-03T13:00:00Z",
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "active"


def test_ca32_rechaza_duracion_de_30_dias_y_un_segundo(client: TestClient) -> None:
    response = crear_reserva(
        client,
        start="2026-11-03T13:00:00Z",
        end="2026-12-03T13:00:01Z",
    )

    assert_error(response, status=422, code="DURATION_TOO_LONG")


def test_ca33_acepta_anticipacion_de_exactamente_30_dias(client: TestClient) -> None:
    # El reloj más 30 días exactos.
    response = crear_reserva(
        client,
        start="2026-12-02T12:00:00Z",
        end="2026-12-02T13:00:00Z",
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "active"


def test_ca34_rechaza_anticipacion_de_30_dias_y_un_segundo(client: TestClient) -> None:
    response = crear_reserva(
        client,
        start="2026-12-02T12:00:01Z",
        end="2026-12-02T13:00:00Z",
    )

    assert_error(response, status=422, code="TOO_FAR_AHEAD")

"""Creación válida y casos aceptados: CA-02, CA-07, CA-08, CA-09.

Reglas cubiertas: R-01, R-02, R-03 (límites consecutivos), R-06, S-02.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from helpers import (
    BASE_END_UTC,
    BASE_START_UTC,
    CLOCK_NOW,
    REQUESTER_BASE,
    REQUESTER_OTRO,
    crear_base,
    crear_reserva,
    parse_utc,
)


def test_ca02_creacion_valida_devuelve_201_activa_y_horas_en_utc(client: TestClient) -> None:
    response = crear_reserva(client)

    assert response.status_code == 201, response.text
    reserva = response.json()
    assert isinstance(reserva["id"], int)
    assert reserva["id"] >= 1, "el sistema asigna el identificador (sección 7.2)"
    assert reserva["unit_id"] == "MIC-01"
    assert reserva["requester"] == REQUESTER_BASE
    assert reserva["status"] == "active"
    # S-02: la respuesta devuelve UTC con sufijo Z. 10:00-03:00 es 13:00Z.
    assert parse_utc(reserva["start"]) == BASE_START_UTC
    assert parse_utc(reserva["end"]) == BASE_END_UTC
    assert parse_utc(reserva["created_at"]) == CLOCK_NOW, "created_at sale del reloj inyectado (S-08)"
    assert reserva["cancelled_at"] is None, "cancelled_at es null mientras esté activa"


def test_ca02_la_reserva_creada_se_recupera_por_su_id(client: TestClient) -> None:
    creada = crear_base(client)

    response = client.get(f"/reservations/{creada['id']}")

    assert response.status_code == 200, response.text
    assert response.json() == creada


def test_ca07_acepta_el_intervalo_inmediatamente_posterior(client: TestClient) -> None:
    crear_base(client)

    # R-02: el instante fin no pertenece a la reserva, así que 11:00 queda libre.
    response = crear_reserva(
        client,
        requester=REQUESTER_OTRO,
        start="2026-11-03T11:00:00-03:00",
        end="2026-11-03T12:00:00-03:00",
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "active"


def test_ca08_acepta_el_intervalo_inmediatamente_anterior(client: TestClient) -> None:
    crear_base(client)

    response = crear_reserva(
        client,
        requester=REQUESTER_OTRO,
        start="2026-11-03T09:00:00-03:00",
        end="2026-11-03T10:00:00-03:00",
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "active"


def test_ca09_acepta_otra_unidad_en_el_mismo_horario(client: TestClient) -> None:
    base = crear_base(client)

    # R-06: unidades distintas nunca entran en conflicto.
    response = crear_reserva(
        client,
        unit_id="MIC-02",
        requester=REQUESTER_OTRO,
        start="2026-11-03T10:00:00-03:00",
        end="2026-11-03T11:00:00-03:00",
    )

    assert response.status_code == 201, response.text
    creada = response.json()
    assert creada["unit_id"] == "MIC-02"
    assert creada["id"] != base["id"], "el identificador nunca se reutiliza"
    assert parse_utc(creada["start"]) == BASE_START_UTC

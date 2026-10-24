"""Partes del contrato que la sección 10 no cubre con un criterio CA.

Cada prueba se nombra con la regla, validación o supuesto que verifica:
V-02 y S-06 (solicitante), el filtro de `GET /reservations`, su orden, y los 404 y
VALIDATION_ERROR declarados en las secciones 7.3 y 7.4.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from helpers import (
    BASE_END,
    BASE_START,
    CLOCK_NOW,
    REQUESTER_OTRO,
    assert_error,
    cancelar,
    consultar_disponibilidad,
    crear_base,
    crear_base_cancelada,
    crear_reserva,
    parse_utc,
)
from reservas.api import create_app


def test_v02_rechaza_solicitante_de_mas_de_100_caracteres(client: TestClient) -> None:
    response = crear_reserva(client, requester="M" * 101)

    assert_error(response, status=422, code="INVALID_REQUESTER")


def test_v02_acepta_solicitante_de_exactamente_100_caracteres(client: TestClient) -> None:
    requester = "M" * 100

    response = crear_reserva(client, requester=requester)

    assert response.status_code == 201, response.text
    assert response.json()["requester"] == requester


def test_s06_guarda_el_solicitante_sin_espacios_en_los_extremos(client: TestClient) -> None:
    response = crear_reserva(client, requester="  Diana Rojas  ")

    assert response.status_code == 201, response.text
    assert response.json()["requester"] == "Diana Rojas"


def test_v03_rechaza_un_cuerpo_sin_el_campo_end(client: TestClient) -> None:
    response = client.post(
        "/reservations",
        json={"unit_id": "MIC-01", "requester": REQUESTER_OTRO, "start": BASE_START},
    )

    error = assert_error(response, status=422, code="VALIDATION_ERROR")
    # Sección 7.2: en VALIDATION_ERROR, details trae loc, msg y type de cada campo.
    assert error["details"], "details no puede venir vacía en un VALIDATION_ERROR"
    for detalle in error["details"]:
        assert {"loc", "msg", "type"} <= set(detalle), f"detalle incompleto: {detalle!r}"


def test_s05_conserva_las_fracciones_de_segundo_sin_redondear(client: TestClient) -> None:
    response = crear_reserva(
        client,
        start="2026-11-03T10:00:00.123456-03:00",
        end="2026-11-03T11:00:00.500000-03:00",
    )

    assert response.status_code == 201, response.text
    reserva = response.json()
    assert parse_utc(reserva["start"]) == datetime(
        2026, 11, 3, 13, 0, 0, 123456, tzinfo=timezone.utc
    )
    assert parse_utc(reserva["end"]) == datetime(
        2026, 11, 3, 14, 0, 0, 500000, tzinfo=timezone.utc
    )


def test_s10_la_consulta_acepta_un_offset_positivo_en_la_query(client: TestClient) -> None:
    base = crear_base(client)

    # S-10: el cliente codifica el `+` del offset. 18:30+05:00 es 13:30Z.
    response = consultar_disponibilidad(
        client, "MIC-01", "2026-11-03T18:30:00+05:00", "2026-11-03T19:30:00+05:00"
    )

    assert response.status_code == 200, response.text
    cuerpo = response.json()
    assert cuerpo["available"] is False
    assert base["id"] in [conflicto["id"] for conflicto in cuerpo["conflicts"]]


def test_contrato_ignora_los_campos_extra_del_cuerpo(client: TestClient) -> None:
    response = client.post(
        "/reservations",
        json={
            "unit_id": "MIC-01",
            "requester": REQUESTER_OTRO,
            "start": BASE_START,
            "end": BASE_END,
            "status": "cancelled",
            "campo_inventado": 1,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "active", "los campos extra se ignoran (sección 7.2)"


def test_contrato_rechaza_el_filtro_de_unidad_inexistente(client: TestClient) -> None:
    response = client.get("/reservations", params={"unit_id": "XYZ-99"})

    assert_error(response, status=422, code="UNKNOWN_UNIT")


def test_contrato_rechaza_un_estado_de_filtro_invalido(client: TestClient) -> None:
    response = client.get("/reservations", params={"status": "pendiente"})

    assert_error(response, status=422, code="VALIDATION_ERROR")


def test_contrato_filtra_el_historial_por_estado(client: TestClient) -> None:
    cancelada = crear_base_cancelada(client)
    activa = crear_reserva(client, requester=REQUESTER_OTRO)
    assert activa.status_code == 201, activa.text

    activas = client.get("/reservations", params={"status": "active"})
    canceladas = client.get("/reservations", params={"status": "cancelled"})

    assert activas.status_code == 200, activas.text
    assert canceladas.status_code == 200, canceladas.text
    assert [reserva["id"] for reserva in activas.json()] == [activa.json()["id"]]
    assert [reserva["id"] for reserva in canceladas.json()] == [cancelada["id"]]


def test_contrato_ordena_el_historial_por_inicio(client: TestClient) -> None:
    tardia = crear_reserva(
        client, start="2026-11-03T15:00:00-03:00", end="2026-11-03T16:00:00-03:00"
    )
    assert tardia.status_code == 201, tardia.text
    temprana = crear_base(client)

    response = client.get("/reservations")

    assert response.status_code == 200, response.text
    assert [reserva["id"] for reserva in response.json()] == [
        temprana["id"],
        tardia.json()["id"],
    ]


def test_contrato_responde_404_al_consultar_una_reserva_inexistente(client: TestClient) -> None:
    response = client.get("/reservations/999")

    assert_error(response, status=404, code="RESERVATION_NOT_FOUND")


def test_s07_permite_cancelar_una_reserva_cuyo_horario_ya_paso(db_path: Path) -> None:
    """S-07: cancelar no crea ocupación, así que una reserva pasada se puede cancelar.

    Se usa un segundo reloj, posterior al fin de la reserva, sobre el mismo archivo.
    """
    with TestClient(create_app(db_path=db_path, clock=lambda: CLOCK_NOW)) as client:
        base = crear_base(client)

    reloj_posterior = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
    with TestClient(create_app(db_path=db_path, clock=lambda: reloj_posterior)) as client:
        response = cancelar(client, base["id"])

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "cancelled"

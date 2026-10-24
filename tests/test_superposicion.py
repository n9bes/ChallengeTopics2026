"""Rechazo de superposición en la misma unidad: CA-03, CA-04, CA-05, CA-06, CA-10.

Reglas cubiertas: R-03, R-05 y el código `OVERLAP` con `details` (sección 7.4).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from helpers import (
    BASE_END_UTC,
    BASE_START_UTC,
    REQUESTER_OTRO,
    assert_error,
    crear_base,
    crear_reserva,
    parse_utc,
)


def _ids_en_details(error: dict[str, Any]) -> list[int]:
    return [conflicto["reservation_id"] for conflicto in error["details"]]


def test_ca03_rechaza_superposicion_parcial(client: TestClient) -> None:
    base = crear_base(client)

    # Ejemplo de la consigna: con MIC-01 de 10:00 a 11:00, se rechaza 10:30 a 11:30.
    response = crear_reserva(
        client,
        requester=REQUESTER_OTRO,
        start="2026-11-03T10:30:00-03:00",
        end="2026-11-03T11:30:00-03:00",
    )

    error = assert_error(response, status=409, code="OVERLAP")
    assert base["id"] in _ids_en_details(error), (
        f"details debe listar la reserva en conflicto: {error['details']!r}"
    )


def test_ca03_la_superposicion_parcial_no_crea_la_reserva(client: TestClient) -> None:
    base = crear_base(client)

    crear_reserva(
        client,
        requester=REQUESTER_OTRO,
        start="2026-11-03T10:30:00-03:00",
        end="2026-11-03T11:30:00-03:00",
    )

    historial = client.get("/reservations")
    assert historial.status_code == 200, historial.text
    assert [reserva["id"] for reserva in historial.json()] == [base["id"]]


def test_ca04_rechaza_intervalo_contenido(client: TestClient) -> None:
    base = crear_base(client)

    response = crear_reserva(
        client,
        requester=REQUESTER_OTRO,
        start="2026-11-03T10:15:00-03:00",
        end="2026-11-03T10:45:00-03:00",
    )

    error = assert_error(response, status=409, code="OVERLAP")
    assert base["id"] in _ids_en_details(error)


def test_ca05_rechaza_intervalo_envolvente(client: TestClient) -> None:
    base = crear_base(client)

    response = crear_reserva(
        client,
        requester=REQUESTER_OTRO,
        start="2026-11-03T09:00:00-03:00",
        end="2026-11-03T12:00:00-03:00",
    )

    error = assert_error(response, status=409, code="OVERLAP")
    assert base["id"] in _ids_en_details(error)


def test_ca06_rechaza_intervalo_identico(client: TestClient) -> None:
    base = crear_base(client)

    response = crear_reserva(
        client,
        requester=REQUESTER_OTRO,
        start="2026-11-03T10:00:00-03:00",
        end="2026-11-03T11:00:00-03:00",
    )

    error = assert_error(response, status=409, code="OVERLAP")
    assert base["id"] in _ids_en_details(error)


def test_ca10_rechaza_superposicion_expresada_en_otro_offset(client: TestClient) -> None:
    base = crear_base(client)

    # S-02: 13:30Z a 14:30Z es el mismo instante que 10:30 a 11:30 en -03:00.
    response = crear_reserva(
        client,
        requester=REQUESTER_OTRO,
        start="2026-11-03T13:30:00Z",
        end="2026-11-03T14:30:00Z",
    )

    error = assert_error(response, status=409, code="OVERLAP")
    assert base["id"] in _ids_en_details(error)
    conflicto = next(
        detalle for detalle in error["details"] if detalle["reservation_id"] == base["id"]
    )
    assert parse_utc(conflicto["start"]) == BASE_START_UTC
    assert parse_utc(conflicto["end"]) == BASE_END_UTC

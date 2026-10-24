"""Entradas inválidas al crear: CA-11 a CA-18.

Validaciones cubiertas: V-01, V-02, V-03, V-04 y sus códigos de la sección 7.4.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from helpers import BASE_END, BASE_START, assert_error, crear_reserva


def test_ca11_rechaza_unidad_inexistente(client: TestClient) -> None:
    response = crear_reserva(client, unit_id="XYZ-99")

    assert_error(response, status=422, code="UNKNOWN_UNIT")


def test_ca12_rechaza_unidad_con_otra_capitalizacion(client: TestClient) -> None:
    # V-01: la comparación es exacta y sensible a mayúsculas.
    response = crear_reserva(client, unit_id="mic-01")

    assert_error(response, status=422, code="UNKNOWN_UNIT")


def test_ca13_rechaza_solicitante_vacio(client: TestClient) -> None:
    response = crear_reserva(client, requester="")

    assert_error(response, status=422, code="INVALID_REQUESTER")


def test_ca14_rechaza_solicitante_de_solo_espacios(client: TestClient) -> None:
    response = crear_reserva(client, requester="   ")

    assert_error(response, status=422, code="INVALID_REQUESTER")


def test_ca15_rechaza_inicio_sin_offset(client: TestClient) -> None:
    # S-01: el offset es obligatorio; una hora sin offset es VALIDATION_ERROR.
    response = crear_reserva(client, start="2026-11-03T10:00:00", end=BASE_END)

    assert_error(response, status=422, code="VALIDATION_ERROR")


def test_ca16_rechaza_fecha_inexistente(client: TestClient) -> None:
    response = crear_reserva(
        client,
        start="2026-02-30T10:00:00-03:00",
        end="2026-02-30T11:00:00-03:00",
    )

    assert_error(response, status=422, code="VALIDATION_ERROR")


def test_ca17_rechaza_inicio_igual_al_fin(client: TestClient) -> None:
    # V-04: el inicio es estrictamente anterior al fin.
    response = crear_reserva(client, start=BASE_START, end=BASE_START)

    assert_error(response, status=422, code="INVALID_INTERVAL")


def test_ca18_rechaza_inicio_posterior_al_fin(client: TestClient) -> None:
    response = crear_reserva(client, start=BASE_END, end=BASE_START)

    assert_error(response, status=422, code="INVALID_INTERVAL")

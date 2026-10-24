"""Consulta de disponibilidad: CA-26, CA-27, CA-28.

Reglas cubiertas: R-03, R-04, R-07 (la consulta usa la misma lógica que la creación),
`UNIT_NOT_FOUND` de la sección 7.4, y las partes de S-03 y S-04 que eximen a la
consulta de los límites de la creación.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from helpers import (
    BASE_END,
    BASE_START,
    REQUESTER_OTRO,
    assert_error,
    consultar_disponibilidad,
    crear_base,
    crear_base_cancelada,
    crear_reserva,
    parse_utc,
)

# Intervalos de CA-03 a CA-08 más la unidad distinta de CA-09, con el resultado que la
# creación produce según esos criterios.
CASOS = [
    ("ca03_parcial", "MIC-01", "2026-11-03T10:30:00-03:00", "2026-11-03T11:30:00-03:00", False),
    ("ca04_contenida", "MIC-01", "2026-11-03T10:15:00-03:00", "2026-11-03T10:45:00-03:00", False),
    ("ca05_envolvente", "MIC-01", "2026-11-03T09:00:00-03:00", "2026-11-03T12:00:00-03:00", False),
    ("ca06_identica", "MIC-01", "2026-11-03T10:00:00-03:00", "2026-11-03T11:00:00-03:00", False),
    ("ca07_posterior", "MIC-01", "2026-11-03T11:00:00-03:00", "2026-11-03T12:00:00-03:00", True),
    ("ca08_anterior", "MIC-01", "2026-11-03T09:00:00-03:00", "2026-11-03T10:00:00-03:00", True),
    ("otra_unidad", "MIC-02", "2026-11-03T10:00:00-03:00", "2026-11-03T11:00:00-03:00", True),
]
IDS_CASOS = [caso[0] for caso in CASOS]


@pytest.mark.parametrize("unit_id,start,end,disponible_esperado", [caso[1:] for caso in CASOS], ids=IDS_CASOS)
def test_ca26_la_disponibilidad_informa_lo_que_dicta_la_superposicion(
    client: TestClient, unit_id: str, start: str, end: str, disponible_esperado: bool
) -> None:
    base = crear_base(client)

    response = consultar_disponibilidad(client, unit_id, start, end)

    assert response.status_code == 200, response.text
    cuerpo = response.json()
    assert cuerpo["unit_id"] == unit_id
    assert parse_utc(cuerpo["start"]) == datetime.fromisoformat(start)
    assert parse_utc(cuerpo["end"]) == datetime.fromisoformat(end)
    assert cuerpo["available"] is disponible_esperado
    if disponible_esperado:
        assert cuerpo["conflicts"] == [], "conflicts está vacía si available es true"
    else:
        ids_en_conflicto = [conflicto["id"] for conflicto in cuerpo["conflicts"]]
        assert base["id"] in ids_en_conflicto, f"conflicts debe contener la base: {cuerpo['conflicts']!r}"
        inicios = [parse_utc(conflicto["start"]) for conflicto in cuerpo["conflicts"]]
        assert inicios == sorted(inicios), "conflicts viene ordenada por inicio"


@pytest.mark.parametrize("unit_id,start,end,disponible_esperado", [caso[1:] for caso in CASOS], ids=IDS_CASOS)
def test_ca26_la_disponibilidad_coincide_con_el_resultado_de_crear(
    client: TestClient, unit_id: str, start: str, end: str, disponible_esperado: bool
) -> None:
    crear_base(client)
    consulta = consultar_disponibilidad(client, unit_id, start, end)
    assert consulta.status_code == 200, consulta.text

    creacion = crear_reserva(
        client, unit_id=unit_id, requester=REQUESTER_OTRO, start=start, end=end
    )

    # R-07: si la consulta dice disponible, la creación no falla por superposición.
    if consulta.json()["available"]:
        assert creacion.status_code == 201, creacion.text
    else:
        assert_error(creacion, status=409, code="OVERLAP")


def test_ca27_tras_cancelar_la_unidad_queda_disponible(client: TestClient) -> None:
    crear_base_cancelada(client)

    response = consultar_disponibilidad(client, "MIC-01", BASE_START, BASE_END)

    assert response.status_code == 200, response.text
    cuerpo = response.json()
    # R-04: solo las reservas activas ocupan su intervalo.
    assert cuerpo["available"] is True
    assert cuerpo["conflicts"] == []


def test_ca28_rechaza_consultar_una_unidad_inexistente(client: TestClient) -> None:
    response = consultar_disponibilidad(client, "XYZ-99", BASE_START, BASE_END)

    assert_error(response, status=404, code="UNIT_NOT_FOUND")


def test_s03_la_disponibilidad_acepta_un_rango_en_el_pasado(client: TestClient) -> None:
    # S-03: la consulta de disponibilidad acepta cualquier rango.
    response = consultar_disponibilidad(
        client, "MIC-01", "2026-10-01T10:00:00-03:00", "2026-10-01T11:00:00-03:00"
    )

    assert response.status_code == 200, response.text
    assert response.json()["available"] is True


def test_s04_la_disponibilidad_no_aplica_los_limites_de_30_dias(client: TestClient) -> None:
    # S-04: los límites de duración y anticipación aplican al crear, no a la consulta.
    response = consultar_disponibilidad(
        client, "MIC-01", "2027-06-01T10:00:00-03:00", "2027-09-01T11:00:00-03:00"
    )

    assert response.status_code == 200, response.text
    assert response.json()["available"] is True


def test_v04_la_disponibilidad_rechaza_un_intervalo_invertido(client: TestClient) -> None:
    response = consultar_disponibilidad(client, "MIC-01", BASE_END, BASE_START)

    assert_error(response, status=422, code="INVALID_INTERVAL")


def test_v03_la_disponibilidad_rechaza_una_hora_sin_offset(client: TestClient) -> None:
    response = consultar_disponibilidad(
        client, "MIC-01", "2026-11-03T10:00:00", "2026-11-03T11:00:00"
    )

    assert_error(response, status=422, code="VALIDATION_ERROR")


# CA-35 y S-11: en la consulta de disponibilidad la unidad es el recurso de la ruta, así
# que su ausencia gana sobre cualquier problema de `start` o `end`. El orden de evaluación
# de la sección 7.4 aplica solo a la creación.
QUERIES_INVALIDAS = [
    ("start_sin_offset_y_sin_end", "?start=2026-11-03T10:00:00"),
    ("sin_start_ni_end", ""),
    ("start_sin_offset_y_end_sin_offset", "?start=2026-11-03T10:00:00&end=2026-11-03T11:00:00"),
    ("fecha_inexistente", "?start=2026-02-30T10:00:00-03:00&end=2026-02-30T11:00:00-03:00"),
]


@pytest.mark.parametrize(
    "query", [caso[1] for caso in QUERIES_INVALIDAS], ids=[caso[0] for caso in QUERIES_INVALIDAS]
)
def test_ca35_la_unidad_inexistente_da_404_aunque_la_query_sea_invalida(
    client: TestClient, query: str
) -> None:
    response = client.get(f"/units/XYZ-99/availability{query}")

    assert_error(response, status=404, code="UNIT_NOT_FOUND")


@pytest.mark.parametrize(
    "query", [caso[1] for caso in QUERIES_INVALIDAS], ids=[caso[0] for caso in QUERIES_INVALIDAS]
)
def test_ca35_la_unidad_existente_con_la_misma_query_invalida_da_422(
    client: TestClient, query: str
) -> None:
    """Contraste de CA-35: el 404 viene de la unidad, no de responder 404 siempre."""
    response = client.get(f"/units/MIC-01/availability{query}")

    assert_error(response, status=422, code="VALIDATION_ERROR")

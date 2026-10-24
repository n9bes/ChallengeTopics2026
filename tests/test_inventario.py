"""CA-01: inventario precargado (sección 3 y endpoint GET /units de la sección 7.3)."""

from __future__ import annotations

from fastapi.testclient import TestClient

INVENTARIO_ESPERADO = [
    {"id": "FUE-01", "name": "Fuente de alimentación"},
    {"id": "MIC-01", "name": "Microscopio digital"},
    {"id": "MIC-02", "name": "Microscopio digital"},
    {"id": "MUL-01", "name": "Multímetro"},
    {"id": "OSC-01", "name": "Osciloscopio"},
]
IDS_ESPERADOS = [unidad["id"] for unidad in INVENTARIO_ESPERADO]


def test_ca01_inventario_precargado_con_las_cinco_unidades(client: TestClient) -> None:
    response = client.get("/units")

    assert response.status_code == 200, response.text
    unidades = response.json()
    assert isinstance(unidades, list)
    assert len(unidades) == 5, f"se esperaban 5 unidades, hay {len(unidades)}: {unidades!r}"
    # Ordenado por ID (sección 7.3).
    assert [unidad["id"] for unidad in unidades] == IDS_ESPERADOS


def test_ca01_cada_unidad_expone_el_equipo_de_la_seccion_3(client: TestClient) -> None:
    response = client.get("/units")

    assert response.status_code == 200, response.text
    assert response.json() == INVENTARIO_ESPERADO

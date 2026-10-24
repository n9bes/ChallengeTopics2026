"""Filtros de `GET /reservations`: CA-36.

Regla cubierta: S-12 de `docs/spec.md`. Un filtro presente pero vacío se valida, no se
ignora. `unit_id=` es una unidad que no existe en el inventario (V-01) y `status=` no es
`active` ni `cancelled`, así que cae en el `VALIDATION_ERROR` de la sección 7.4.

Las variantes con valor no vacío (`unit_id=XYZ-99`, `status=pendiente`) y el orden del
historial viven en `test_contrato_sin_criterio.py`, que cubre las partes del contrato sin
criterio CA propio.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from helpers import assert_error, crear_base


def test_ca36_rechaza_el_filtro_de_unidad_vacio(client: TestClient) -> None:
    response = client.get("/reservations?unit_id=")

    assert_error(response, status=422, code="UNKNOWN_UNIT")


def test_ca36_rechaza_el_filtro_de_estado_vacio(client: TestClient) -> None:
    response = client.get("/reservations?status=")

    assert_error(response, status=422, code="VALIDATION_ERROR")


def test_ca36_el_filtro_vacio_no_equivale_a_no_enviar_filtro(client: TestClient) -> None:
    """Contraste de S-12: sin filtros hay historial completo; con filtro vacío hay 422."""
    base = crear_base(client)

    sin_filtros = client.get("/reservations")

    assert sin_filtros.status_code == 200, sin_filtros.text
    assert [reserva["id"] for reserva in sin_filtros.json()] == [base["id"]]
    assert_error(client.get("/reservations?unit_id="), status=422, code="UNKNOWN_UNIT")
    assert_error(client.get("/reservations?status="), status=422, code="VALIDATION_ERROR")

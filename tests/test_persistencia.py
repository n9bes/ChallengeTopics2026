"""Persistencia tras reinicio: CA-29 y CA-30.

Sección 7.1: crear dos aplicaciones sobre el mismo `db_path` equivale a reiniciar el
servidor. Sección 8: nunca se borra una reserva.

El primer cliente se cierra antes de construir la segunda aplicación: en Windows
SQLite mantiene el archivo tomado y la segunda conexión fallaría.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from helpers import (
    BASE_END,
    BASE_START,
    REQUESTER_BASE,
    REQUESTER_OTRO,
    REQUESTER_TERCERO,
    assert_error,
    cancelar,
    crear_reserva,
)

# Segundo intervalo, sin superposición con la base, usado para la reserva cancelada.
OTRO_START = "2026-11-03T15:00:00-03:00"
OTRO_END = "2026-11-03T16:00:00-03:00"


def _sembrar_activa_y_cancelada(make_app: Callable[[], FastAPI]) -> dict[str, Any]:
    """Crea una reserva activa y otra cancelada con una aplicación, y la cierra."""
    with TestClient(make_app()) as client:
        activa = crear_reserva(client, requester=REQUESTER_BASE)
        assert activa.status_code == 201, activa.text

        por_cancelar = crear_reserva(client, requester=REQUESTER_OTRO, start=OTRO_START, end=OTRO_END)
        assert por_cancelar.status_code == 201, por_cancelar.text

        cancelacion = cancelar(client, por_cancelar.json()["id"])
        assert cancelacion.status_code == 200, cancelacion.text

    return {"activa": activa.json(), "cancelada": cancelacion.json()}


def test_ca29_las_reservas_sobreviven_al_reinicio(make_app: Callable[[], FastAPI]) -> None:
    sembradas = _sembrar_activa_y_cancelada(make_app)

    with TestClient(make_app()) as client:
        response = client.get("/reservations")

        assert response.status_code == 200, response.text
        recuperadas = {reserva["id"]: reserva for reserva in response.json()}

    assert set(recuperadas) == {sembradas["activa"]["id"], sembradas["cancelada"]["id"]}
    assert recuperadas[sembradas["activa"]["id"]] == sembradas["activa"]
    assert recuperadas[sembradas["cancelada"]["id"]] == sembradas["cancelada"]
    assert recuperadas[sembradas["activa"]["id"]]["status"] == "active"
    assert recuperadas[sembradas["cancelada"]["id"]]["status"] == "cancelled"


def test_ca29_el_inventario_no_se_duplica_al_reiniciar(make_app: Callable[[], FastAPI]) -> None:
    # Sección 8: las unidades se cargan sin duplicar si ya existen.
    with TestClient(make_app()) as client:
        primera = client.get("/units")
        assert primera.status_code == 200, primera.text

    with TestClient(make_app()) as client:
        segunda = client.get("/units")

        assert segunda.status_code == 200, segunda.text
        assert segunda.json() == primera.json()


def test_ca30_tras_el_reinicio_la_activa_sigue_ocupando_su_intervalo(
    make_app: Callable[[], FastAPI],
) -> None:
    sembradas = _sembrar_activa_y_cancelada(make_app)

    with TestClient(make_app()) as client:
        response = crear_reserva(
            client, requester=REQUESTER_TERCERO, start=BASE_START, end=BASE_END
        )

        error = assert_error(response, status=409, code="OVERLAP")
        ids_en_conflicto = [conflicto["reservation_id"] for conflicto in error["details"]]
        assert sembradas["activa"]["id"] in ids_en_conflicto


def test_ca30_tras_el_reinicio_la_cancelada_no_ocupa_su_intervalo(
    make_app: Callable[[], FastAPI],
) -> None:
    sembradas = _sembrar_activa_y_cancelada(make_app)

    with TestClient(make_app()) as client:
        response = crear_reserva(
            client, requester=REQUESTER_TERCERO, start=OTRO_START, end=OTRO_END
        )

        assert response.status_code == 201, response.text
        nueva = response.json()

    assert nueva["status"] == "active"
    assert nueva["id"] != sembradas["cancelada"]["id"], "el identificador nunca se reutiliza"

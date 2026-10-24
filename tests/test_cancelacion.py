"""Cancelación: CA-21 a CA-25.

Reglas cubiertas: R-04, R-08, R-09 y los códigos `ALREADY_CANCELLED` y
`RESERVATION_NOT_FOUND` de la sección 7.4.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from helpers import (
    BASE_END_UTC,
    BASE_START_UTC,
    REQUESTER_BASE,
    REQUESTER_OTRO,
    assert_error,
    cancelar,
    crear_base,
    crear_base_cancelada,
    crear_reserva,
    parse_utc,
)


def test_ca21_cancelar_conserva_el_registro_completo(client: TestClient) -> None:
    base = crear_base(client)

    respuesta_cancelacion = cancelar(client, base["id"])
    assert respuesta_cancelacion.status_code == 200, respuesta_cancelacion.text

    consulta = client.get(f"/reservations/{base['id']}")
    assert consulta.status_code == 200, consulta.text

    for reserva in (respuesta_cancelacion.json(), consulta.json()):
        assert reserva["status"] == "cancelled"
        assert reserva["cancelled_at"] is not None, "R-08 registra el momento de cancelación"
        parse_utc(reserva["cancelled_at"])
        # R-08: conserva identificador y datos.
        assert reserva["id"] == base["id"]
        assert reserva["unit_id"] == base["unit_id"]
        assert reserva["requester"] == REQUESTER_BASE
        assert parse_utc(reserva["start"]) == BASE_START_UTC
        assert parse_utc(reserva["end"]) == BASE_END_UTC


def test_ca22_cancelar_libera_el_intervalo(client: TestClient) -> None:
    cancelada = crear_base_cancelada(client)

    # R-04: una reserva cancelada no bloquea nada.
    response = crear_reserva(client, requester=REQUESTER_OTRO)

    assert response.status_code == 201, response.text
    nueva = response.json()
    assert nueva["status"] == "active"
    assert nueva["id"] != cancelada["id"], "el identificador nunca se reutiliza"


def test_ca23_el_historial_lista_la_cancelada_y_la_nueva_activa(client: TestClient) -> None:
    cancelada = crear_base_cancelada(client)
    nueva = crear_reserva(client, requester=REQUESTER_OTRO)
    assert nueva.status_code == 201, nueva.text
    nueva_id = nueva.json()["id"]

    response = client.get("/reservations", params={"unit_id": "MIC-01"})

    assert response.status_code == 200, response.text
    estados = {reserva["id"]: reserva["status"] for reserva in response.json()}
    assert estados == {cancelada["id"]: "cancelled", nueva_id: "active"}


def test_ca24_rechaza_cancelar_dos_veces(client: TestClient) -> None:
    cancelada = crear_base_cancelada(client)

    response = cancelar(client, cancelada["id"])

    # R-09: solo se cancela una reserva activa.
    assert_error(response, status=409, code="ALREADY_CANCELLED")


def test_ca25_rechaza_cancelar_una_reserva_inexistente(client: TestClient) -> None:
    response = cancelar(client, 999)

    assert_error(response, status=404, code="RESERVATION_NOT_FOUND")

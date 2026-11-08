"""
RF 5.5 - Aceptar o rechazar ofertas de conductor
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

CLIENTE_ID = "550e8400-e29b-41d4-a716-446655440000"
CONDUCTOR_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
OTRO_CLIENTE_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def _crear_solicitud_y_oferta():
    res_sol = client.post("/solicitudes", json={
        "cliente_id": CLIENTE_ID,
        "origen_latitud": -27.4512,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "AUTO",
    })
    assert res_sol.status_code == 201
    solicitud_id = res_sol.json()["solicitud_id"]

    res_oferta = client.post("/ofertas/", json={
        "id_solicitud": solicitud_id,
        "conductor_id": CONDUCTOR_ID,
        "tiempo_expiracion_seg": 30,
    })
    assert res_oferta.status_code == 201
    oferta_id = res_oferta.json()["id_oferta"]

    return solicitud_id, oferta_id


def test_aceptar_oferta_exitosamente():
    solicitud_id, oferta_id = _crear_solicitud_y_oferta()

    respuesta = client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "ACEPTAR",
    })

    assert respuesta.status_code == 200
    resultado = respuesta.json()
    assert resultado["id_oferta"] == oferta_id
    assert resultado["id_solicitud"] == solicitud_id
    assert resultado["estado_oferta"] == "ACEPTADA"
    assert resultado["estado_solicitud"] == "ACEPTADA"


def test_rechazar_oferta_exitosamente():
    solicitud_id, oferta_id = _crear_solicitud_y_oferta()

    respuesta = client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "RECHAZAR",
    })

    assert respuesta.status_code == 200
    resultado = respuesta.json()
    assert resultado["estado_oferta"] == "RECHAZADA"
    assert resultado["estado_solicitud"] == "PENDIENTE"


def test_responder_oferta_no_existente():
    respuesta = client.patch("/ofertas/id-inexistente/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "ACEPTAR",
    })
    assert respuesta.status_code == 404


def test_responder_oferta_cliente_no_autorizado():
    _, oferta_id = _crear_solicitud_y_oferta()

    respuesta = client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": OTRO_CLIENTE_ID,
        "accion": "ACEPTAR",
    })
    assert respuesta.status_code == 403


def test_responder_oferta_ya_respondida():
    _, oferta_id = _crear_solicitud_y_oferta()

    client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "ACEPTAR",
    })

    respuesta = client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "RECHAZAR",
    })
    assert respuesta.status_code == 409


def test_responder_oferta_accion_invalida():
    _, oferta_id = _crear_solicitud_y_oferta()

    respuesta = client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "IGNORAR",
    })
    assert respuesta.status_code == 422

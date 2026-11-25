import pytest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from app.main import app
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud
from app.services.ofertas_service import emitir_lote_ofertas

client = TestClient(app)


def test_inicio():
    respuesta = client.get("/")

    assert respuesta.status_code == 200

    assert respuesta.json() == {
        "mensaje": "API del Grupo 13 - Modulo M5"
    }


def test_crear_solicitud(db_pruebas):
    datos = {
        "cliente_id": "550e8400-e29b-41d4-a716-446655440000",
        "origen_latitud": -27.4512,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "AUTO"
    }

    respuesta = client.post("/solicitudes", json=datos)

    assert respuesta.status_code == 201

    resultado = respuesta.json()

    assert resultado["mensaje"] == "Solicitud creada correctamente"
    assert resultado["estado"] == "PENDIENTE"

    solicitud_id = resultado["solicitud_id"]
    assert str(UUID(solicitud_id)) == solicitud_id

    solicitud_guardada = db_pruebas.get(Solicitud, solicitud_id)

    assert solicitud_guardada is not None
    assert solicitud_guardada.cliente_id == datos["cliente_id"]
    assert solicitud_guardada.origen_latitud == datos["origen_latitud"]
    assert solicitud_guardada.origen_longitud == datos["origen_longitud"]
    assert solicitud_guardada.destino_latitud == datos["destino_latitud"]
    assert solicitud_guardada.destino_longitud == datos["destino_longitud"]
    assert solicitud_guardada.tipo_vehiculo == datos["tipo_vehiculo"]
    assert solicitud_guardada.estado == "PENDIENTE"

from fastapi.testclient import TestClient
from app.main import app




def test_rechazar_tipo_vehiculo_invalido():
    datos = {
        "cliente_id": "550e8400-e29b-41d4-a716-446655440000",
        "origen_latitud": -27.4512,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "AVION"
    }

    respuesta = client.post("/solicitudes", json=datos)

    assert respuesta.status_code == 422


def test_rechazar_coordenadas_invalidas():
    datos = {
        "cliente_id": "550e8400-e29b-41d4-a716-446655440000",
        "origen_latitud": -100,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "AUTO"
    }

    respuesta = client.post("/solicitudes", json=datos)

    assert respuesta.status_code == 422

# ── RF 5.4 - Oferta con vencimiento ─────────────────────────────────────────

def test_emitir_lote_y_listar_ofertas_solicitud(db_pruebas):
    solicitud = Solicitud(
        cliente_id="550e8400-e29b-41d4-a716-446655440000",
        origen_latitud=-27.4512,
        origen_longitud=-58.9866,
        destino_latitud=-27.4601,
        destino_longitud=-58.9735,
        tipo_vehiculo="AUTO",
        estado="buscando",
    )
    db_pruebas.add(solicitud)
    db_pruebas.commit()
    db_pruebas.refresh(solicitud)

    conductor_1 = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    conductor_2 = "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22"
    lote = emitir_lote_ofertas(db_pruebas, solicitud, [conductor_1, conductor_2])

    assert len(lote.ofertas) == 2

    respuesta = client.get(f"/solicitudes/{solicitud.solicitud_id}/ofertas")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos) == 2
    assert datos[0]["estado"] == "pendiente"

    creada = datetime.fromisoformat(datos[0]["creada_en"])
    vence = datetime.fromisoformat(datos[0]["vence_en"])
    assert int((vence - creada).total_seconds()) == 30


def test_oferta_expira_automaticamente_al_consultar(db_pruebas):
    conductor_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    solicitud = Solicitud(
        cliente_id="550e8400-e29b-41d4-a716-446655440000",
        origen_latitud=-27.4512,
        origen_longitud=-58.9866,
        destino_latitud=-27.4601,
        destino_longitud=-58.9735,
        tipo_vehiculo="MOTO",
        estado="buscando",
    )
    db_pruebas.add(solicitud)
    db_pruebas.commit()
    db_pruebas.refresh(solicitud)

    ahora = datetime.now(timezone.utc)
    oferta_expirada = Oferta(
        solicitud_id=solicitud.solicitud_id,
        conductor_id=conductor_id,
        estado="pendiente",
        creada_en=ahora - timedelta(seconds=45),
        vence_en=ahora - timedelta(seconds=15),
    )
    db_pruebas.add(oferta_expirada)
    db_pruebas.commit()

    respuesta = client.get(f"/conductores/{conductor_id}/ofertas?estado=vencida")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos) == 1
    assert datos[0]["estado"] == "vencida"


# ── RF 5.5 - Aceptar o rechazar ofertas ─────────────────────────────────────

CLIENTE_ID = "550e8400-e29b-41d4-a716-446655440000"
CONDUCTOR_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
OTRO_CLIENTE_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def _crear_solicitud_y_oferta():
    """Helper: crea una solicitud y una oferta PENDIENTE, retorna sus IDs."""
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

@pytest.mark.skip(reason="Pendiente migracion de RF-5.5 al contrato v1.5.0")
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

@pytest.mark.skip(reason="Pendiente migracion de RF-5.5 al contrato v1.5.0")
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

@pytest.mark.skip(reason="Pendiente migracion de RF-5.5 al contrato v1.5.0")
def test_responder_oferta_no_existente():
    respuesta = client.patch("/ofertas/id-inexistente/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "ACEPTAR",
    })
    assert respuesta.status_code == 404

@pytest.mark.skip(reason="Pendiente migracion de RF-5.5 al contrato v1.5.0")
def test_responder_oferta_cliente_no_autorizado():
    _, oferta_id = _crear_solicitud_y_oferta()

    respuesta = client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": OTRO_CLIENTE_ID,
        "accion": "ACEPTAR",
    })
    assert respuesta.status_code == 403

@pytest.mark.skip(reason="Pendiente migracion de RF-5.5 al contrato v1.5.0")
def test_responder_oferta_ya_respondida():
    _, oferta_id = _crear_solicitud_y_oferta()

    # Primera respuesta (aceptar)
    client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "ACEPTAR",
    })

    # Segunda respuesta sobre la misma oferta
    respuesta = client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "RECHAZAR",
    })
    assert respuesta.status_code == 409

@pytest.mark.skip(reason="Pendiente migracion de RF-5.5 al contrato v1.5.0")
def test_responder_oferta_accion_invalida():
    _, oferta_id = _crear_solicitud_y_oferta()

    respuesta = client.patch(f"/ofertas/{oferta_id}/respuesta", json={
        "cliente_id": CLIENTE_ID,
        "accion": "IGNORAR",
    })
    assert respuesta.status_code == 422


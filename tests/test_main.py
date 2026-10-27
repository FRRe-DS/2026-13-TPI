
from uuid import UUID

from fastapi.testclient import TestClient
from app.main import app
from app.models.solicitud import Solicitud

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

client = TestClient(app)


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

def test_crear_oferta_exitosa():
    datos_solicitud = {
        "cliente_id": "550e8400-e29b-41d4-a716-446655440000",
        "origen_latitud": -27.4512,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "AUTO"
    }
    res_solicitud = client.post("/solicitudes", json=datos_solicitud)
    assert res_solicitud.status_code == 201
    solicitud_id = res_solicitud.json()["solicitud_id"]

    # Probar la creación de la oferta asociada
    datos_oferta = {
        "id_solicitud": solicitud_id,
        "conductor_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "tiempo_expiracion_seg": 30
    }
    respuesta = client.post("/ofertas/", json=datos_oferta)

    # 3. Validar estado y estructura de la respuesta
    assert respuesta.status_code == 201
    resultado = respuesta.json()
    assert resultado["id_solicitud"] == solicitud_id
    assert resultado["conductor_id"] == datos_oferta["conductor_id"]
    assert resultado["estado"] == "PENDIENTE"
    assert "id_oferta" in resultado
    assert "fecha_expiracion" in resultado


def test_rechazar_oferta_datos_incompletos():
    # Verificación de validación al omitir campos obligatorios
    respuesta = client.post("/ofertas/", json={"tiempo_expiracion_seg": 30})
    assert respuesta.status_code == 422



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

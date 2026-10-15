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
        "origen": "UTN Resistencia",
        "destino": "Plaza 25 de Mayo",
        "tipo_vehiculo": "auto"
    }

    respuesta = client.post("/solicitudes", json=datos)

    assert respuesta.status_code == 201

    resultado = respuesta.json()

    assert resultado["mensaje"] == "Solicitud creada correctamente"
    assert resultado["estado"] == "pendiente"
    assert isinstance(resultado["id"], int)

    solicitud_guardada = db_pruebas.get(Solicitud, resultado["id"])

    assert solicitud_guardada is not None
    assert solicitud_guardada.origen == datos["origen"]
    assert solicitud_guardada.destino == datos["destino"]
    assert solicitud_guardada.tipo_vehiculo == datos["tipo_vehiculo"]
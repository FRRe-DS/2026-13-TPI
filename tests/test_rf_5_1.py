import pytest
import httpx

from uuid import uuid4
from fastapi import HTTPException
from unittest.mock import patch
from app.services.clientes import validar_estado_cuenta

from fastapi.testclient import TestClient
from app.main import app
from app.auth import validar_cliente
from app.models.solicitud import Solicitud
from app.models.evento_notificacion import EventoNotificacion
from datetime import datetime, timezone, timedelta
from app.services.notificaciones import procesar_evento

def test_cliente_activo(monkeypatch):
    # Configura una dirección ficticia de M2 para la prueba.
    monkeypatch.setattr(
        "app.services.clientes.M2_URL",
        "http://m2-prueba"
    )

    # Simula una respuesta exitosa de M2.
    with patch("app.services.clientes.httpx.get") as mock:
        mock.return_value = httpx.Response(
            200, json={"estado": "ACTIVO"}
        )

        # La validación debe finalizar sin generar excepciones.
        validar_estado_cuenta(uuid4(), "token-prueba")

def test_cliente_bloqueado(monkeypatch):
    monkeypatch.setattr(
        "app.services.clientes.M2_URL",
        "http://m2-prueba"
    )

    # Simula un cliente con su cuenta bloqueada.
    with patch("app.services.clientes.httpx.get") as mock:
        mock.return_value = httpx.Response(
            200, json={"estado": "BLOQUEADO"}
        )

        # La validación debe rechazar al cliente con un error 422.
        with pytest.raises(HTTPException) as error:
            validar_estado_cuenta(uuid4(), "token-prueba")

        assert error.value.status_code == 422

def test_cliente_inexistente(monkeypatch):
    monkeypatch.setattr(
        "app.services.clientes.M2_URL",
        "http://m2-prueba"
    )

    # Simula que M2 no encuentra al cliente.
    with patch("app.services.clientes.httpx.get") as mock:
        mock.return_value = httpx.Response(404)

        # M5 debe rechazar la solicitud con un error 422.
        with pytest.raises(HTTPException) as error:
            validar_estado_cuenta(uuid4(), "token-prueba")

        assert error.value.status_code == 422

def test_m2_no_disponible(monkeypatch):
    monkeypatch.setattr(
        "app.services.clientes.M2_URL",
        "http://m2-prueba"
    )

    # Simula un fallo de conexión con M2.
    with patch("app.services.clientes.httpx.get") as mock:
        mock.side_effect = httpx.ConnectError("Error de conexión")

        # M5 debe responder con un error 503.
        with pytest.raises(HTTPException) as error:
            validar_estado_cuenta(uuid4(), "token-prueba")

        assert error.value.status_code == 503

@pytest.fixture
def cliente_api(db_pruebas, monkeypatch):
    # Simula la identidad de un cliente autenticado por M1.
    app.dependency_overrides[validar_cliente] = lambda: {
        "sub": str(cliente_id)
    }

    cliente_id = uuid4()

    # Simula la autenticación de servicio y la validación de M2.
    monkeypatch.setattr(
        "app.main.obtener_token_servicio",
        lambda: "token-prueba"
    )
    monkeypatch.setattr(
        "app.main.validar_estado_cuenta",
        lambda *args: None
    )
    # Simula que M8 no está disponible temporalmente.
    monkeypatch.setattr(
        "app.services.notificaciones.enviar_evento",
        lambda *args: ("REINTENTAR", 60)
    )
    # Simula el inicio de RF-5.3 sin depender de M4.
    monkeypatch.setattr(
        "app.main.ejecutar_busqueda",
        lambda *args: None
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(validar_cliente, None)


# Datos utilizados para las solicitudes de prueba.
DATOS_VIAJE = {
    "origen_latitud": -27.45,
    "origen_longitud": -59.02,
    "destino_latitud": -27.46,
    "destino_longitud": -59.03,
    "tipo_vehiculo": "AUTO"
}

HEADERS = {"Idempotency-Key": "clave-prueba-001"}


def test_solicitud_nueva(cliente_api):
    # Una solicitud nueva debe registrarse correctamente.
    respuesta = cliente_api.post(
        "/api/v1/solicitudes", json=DATOS_VIAJE, headers=HEADERS
    )

    assert respuesta.status_code == 201


def test_solicitud_repetida(cliente_api, db_pruebas):
    # Repite la misma petición utilizando la misma clave.
    primera = cliente_api.post(
        "/api/v1/solicitudes", json=DATOS_VIAJE, headers=HEADERS
    )
    segunda = cliente_api.post(
        "/api/v1/solicitudes", json=DATOS_VIAJE, headers=HEADERS
    )

    assert primera.status_code == 201
    assert segunda.status_code == 200

    # Ambas respuestas deben identificar la misma solicitud.
    assert primera.json()["solicitud_id"] == segunda.json()["solicitud_id"]

    # Comprueba que no se hayan creado registros duplicados.
    assert db_pruebas.query(Solicitud).count() == 1


def test_idempotencia_conflicto(cliente_api, db_pruebas):
    # Reutiliza la misma clave, pero modifica los datos.
    primera = cliente_api.post(
        "/api/v1/solicitudes", json=DATOS_VIAJE, headers=HEADERS
    )

    datos_modificados = {**DATOS_VIAJE, "tipo_vehiculo": "MOTO"}

    segunda = cliente_api.post(
        "/api/v1/solicitudes", json=datos_modificados, headers=HEADERS
    )

    assert primera.status_code == 201
    assert segunda.status_code == 409
    assert db_pruebas.query(Solicitud).count() == 1

def test_estimacion_tarifa(cliente_api, monkeypatch, db_pruebas):
    # Simula la distancia y duración proporcionadas por M4.
    monkeypatch.setattr(
        "app.main.consultar_distancia",
        lambda *args: {
            "distancia_estimada_km": 8.5,
            "eta_minutos": 15
        }
    )

    # Simula la tarifa calculada por M7.
    monkeypatch.setattr(
        "app.main.consultar_tarifa",
        lambda *args: {
            "moneda": "ARS",
            "desglose": {"total": 5700}
        }
    )

    respuesta = cliente_api.post(
        "/api/v1/solicitudes/estimacion",
        json=DATOS_VIAJE
    )

    # Verifica los datos de la estimación.
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "moneda": "ARS",
        "total_estimado": 5700,
        "distancia_estimada_km": 8.5,
        "duracion_estimada_min": 15
    }

    # Estimar una tarifa no debe registrar una solicitud.
    assert db_pruebas.query(Solicitud).count() == 0

def test_registro_evento_notificacion(cliente_api, db_pruebas):

    respuesta = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    assert respuesta.status_code == 201

    # Verifica que se haya registrado un único evento.
    assert db_pruebas.query(EventoNotificacion).count() == 1

    evento = db_pruebas.query(EventoNotificacion).first()

    # Verifica la relación entre el evento y la solicitud.
    assert evento.solicitud_id == respuesta.json()["solicitud_id"]
    assert evento.tipo == "VIAJE_SOLICITADO"
    assert evento.estado == "PENDIENTE"
    assert evento.intentos == 1

    # Verifica la consistencia del mensaje almacenado.
    assert evento.cuerpo["eventoId"] == evento.evento_id
    assert evento.cuerpo["solicitudId"] == evento.solicitud_id


def test_evento_notificacion_no_duplicado(cliente_api, db_pruebas):

    # Envía dos veces la misma solicitud.
    primera = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    segunda = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    assert primera.status_code == 201
    assert segunda.status_code == 200

    # Debe existir una sola solicitud y un solo evento.
    assert db_pruebas.query(Solicitud).count() == 1
    assert db_pruebas.query(EventoNotificacion).count() == 1

def test_notificacion_enviada(cliente_api, db_pruebas, monkeypatch):

    # Simula que M8 recibe correctamente el evento.
    monkeypatch.setattr(
        "app.services.notificaciones.enviar_evento",
        lambda *args: ("ENVIADO", 0)
    )

    respuesta = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    assert respuesta.status_code == 201

    evento = db_pruebas.query(EventoNotificacion).first()

    assert evento.estado == "ENVIADO"
    assert evento.intentos == 1
    assert evento.fecha_envio is not None


def test_notificacion_error_temporal(cliente_api, db_pruebas):

    respuesta = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    # La solicitud se registra aunque M8 no esté disponible.
    assert respuesta.status_code == 201
    assert db_pruebas.query(Solicitud).count() == 1

    evento = db_pruebas.query(EventoNotificacion).first()

    assert evento.estado == "PENDIENTE"
    assert evento.intentos == 1
    assert evento.fecha_envio is None


def test_notificacion_error_definitivo(
    cliente_api, db_pruebas, monkeypatch
):

    # Simula un error definitivo de M8.
    monkeypatch.setattr(
        "app.services.notificaciones.enviar_evento",
        lambda *args: ("ERROR", 0)
    )

    respuesta = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    assert respuesta.status_code == 201
    assert db_pruebas.query(Solicitud).count() == 1

    evento = db_pruebas.query(EventoNotificacion).first()

    assert evento.estado == "ERROR"
    assert evento.intentos == 1
    assert evento.fecha_envio is None

def test_reintentos_notificacion(cliente_api, db_pruebas):

    respuesta = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    assert respuesta.status_code == 201

    evento = db_pruebas.query(EventoNotificacion).first()

    evento_id = evento.evento_id
    cuerpo_original = evento.cuerpo.copy()

    # No debe reintentar antes del tiempo establecido.
    procesar_evento(db_pruebas, evento, "token-prueba")
    assert evento.intentos == 1

    # Simula el transcurso del tiempo entre intentos.
    for _ in range(2):

        evento.proximo_intento = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )

        db_pruebas.commit()

        procesar_evento(db_pruebas, evento, "token-prueba")

    # Verifica el límite de intentos y la idempotencia.
    assert evento.intentos == 3
    assert evento.estado == "ERROR"
    assert evento.evento_id == evento_id
    assert evento.cuerpo == cuerpo_original
    assert db_pruebas.query(EventoNotificacion).count() == 1

def test_inicio_busqueda(cliente_api, monkeypatch):

    solicitudes_buscadas = []

    # Registra las solicitudes que inician una búsqueda.
    monkeypatch.setattr(
        "app.main.ejecutar_busqueda",
        lambda solicitud_id: solicitudes_buscadas.append(solicitud_id)
    )

    primera = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    segunda = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE,
        headers=HEADERS
    )

    assert primera.status_code == 201
    assert segunda.status_code == 200

    # La solicitud debe iniciar una única búsqueda.
    assert solicitudes_buscadas == [
        primera.json()["solicitud_id"]
    ]

@pytest.mark.parametrize("campo, valor", [
    ("tipo_vehiculo", "AVION"),
    ("origen_latitud", -100)
])
def test_datos_solicitud_invalidos(cliente_api, campo, valor):

    # Modifica un dato válido para comprobar su validación.
    datos = DATOS_VIAJE.copy()
    datos[campo] = valor

    respuesta = cliente_api.post(
        "/api/v1/solicitudes",
        json=datos,
        headers=HEADERS
    )

    assert respuesta.status_code == 422

def test_idempotency_key_ausente(cliente_api):

    respuesta = cliente_api.post(
        "/api/v1/solicitudes",
        json=DATOS_VIAJE
    )

    assert respuesta.status_code == 400
"""
RF 5.3 - Búsqueda de candidatos (con un M4 simulado)
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.despacho import HistorialDespacho
from app.models.solicitud import Solicitud
from app.schemas.busqueda import ResultadoBusquedaM4
from app.services import clientes_m4
from app.services.clientes_m4 import ErrorIntegracionM4, buscar_candidatos

client = TestClient(app)

CLIENTE_ID = "550e8400-e29b-41d4-a716-446655440000"
CONDUCTOR_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CONDUCTOR_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
CONDUCTOR_MOTO = "cccccccc-cccc-cccc-cccc-cccccccccccc"
SOLICITUD_INEXISTENTE = "99999999-9999-9999-9999-999999999999"


@pytest.fixture(autouse=True)
def usar_db_de_pruebas(db_pruebas):
    yield


def _candidato(conductor_id, distancia_km, tipo="AUTO"):
    return {
        "conductor_id": conductor_id,
        "distancia_origen_km": distancia_km,
        "eta_retiro_minutos": 3,
        "tipo_vehiculo": tipo,
    }


def _respuesta_m4(conductores, radio=5):
    return ResultadoBusquedaM4.model_validate({
        "conductores": conductores,
        "radio_aplicado_km": radio,
        "generado_en": "2026-11-22T21:00:00Z",
    })


def _crear_solicitud():
    res = client.post("/solicitudes", json={
        "cliente_id": CLIENTE_ID,
        "origen_latitud": -27.4512,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "AUTO",
    })
    assert res.status_code == 201
    return res.json()["solicitud_id"]


def _estados_del_historial(db, solicitud_id):
    filas = db.query(HistorialDespacho).filter(
        HistorialDespacho.id_solicitud == solicitud_id
    ).all()
    return [fila.estado_nuevo for fila in filas]


# ── Servicio de búsqueda (M4 simulado) ──────────────────────────────────────

def test_busqueda_devuelve_candidatos_ordenados_y_compatibles(db_pruebas, monkeypatch):
    llamadas = []

    def m4_falso(latitud, longitud, tipo, **kwargs):
        llamadas.append((latitud, longitud, tipo))
        return _respuesta_m4([
            _candidato(CONDUCTOR_B, 2.0),
            _candidato(CONDUCTOR_A, 0.5),
            _candidato(CONDUCTOR_MOTO, 0.1, tipo="MOTO"),
            _candidato(CONDUCTOR_A, 0.6),
        ], radio=6.5)

    monkeypatch.setattr(clientes_m4, "buscar_candidatos", m4_falso)
    solicitud_id = _crear_solicitud()

    respuesta = client.post(f"/solicitudes/{solicitud_id}/busqueda")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "buscando"
    assert cuerpo["radio_aplicado_km"] == 6.5
    ids = [c["conductor_id"] for c in cuerpo["conductores"]]
    assert ids == [CONDUCTOR_A, CONDUCTOR_B]  # ordenados, sin MOTO y sin repetidos
    assert llamadas == [(-27.4512, -58.9866, "AUTO")]

    assert db_pruebas.get(Solicitud, solicitud_id).estado == "buscando"
    assert "buscando" in _estados_del_historial(db_pruebas, solicitud_id)


def test_busqueda_sin_conductores_deja_sin_disponibilidad(db_pruebas, monkeypatch):
    monkeypatch.setattr(
        clientes_m4, "buscar_candidatos",
        lambda *args, **kwargs: _respuesta_m4([], radio=9.5),
    )
    solicitud_id = _crear_solicitud()

    respuesta = client.post(f"/solicitudes/{solicitud_id}/busqueda")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "sin_disponibilidad"
    assert cuerpo["conductores"] == []
    assert cuerpo["radio_aplicado_km"] == 9.5
    assert db_pruebas.get(Solicitud, solicitud_id).estado == "sin_disponibilidad"
    assert "sin_disponibilidad" in _estados_del_historial(db_pruebas, solicitud_id)


def test_error_de_m4_no_se_toma_como_lista_vacia(db_pruebas, monkeypatch):
    def m4_caido(*args, **kwargs):
        raise ErrorIntegracionM4("M4 no respondió a tiempo (timeout) tras 3 intentos")

    monkeypatch.setattr(clientes_m4, "buscar_candidatos", m4_caido)
    solicitud_id = _crear_solicitud()

    respuesta = client.post(f"/solicitudes/{solicitud_id}/busqueda")

    assert respuesta.status_code == 503
    assert db_pruebas.get(Solicitud, solicitud_id).estado == "buscando"
    assert "ERROR_INTEGRACION" in _estados_del_historial(db_pruebas, solicitud_id)


def test_busqueda_de_solicitud_inexistente():
    respuesta = client.post(f"/solicitudes/{SOLICITUD_INEXISTENTE}/busqueda")
    assert respuesta.status_code == 404


def test_busqueda_no_se_puede_iniciar_dos_veces(monkeypatch):
    monkeypatch.setattr(
        clientes_m4, "buscar_candidatos",
        lambda *args, **kwargs: _respuesta_m4([_candidato(CONDUCTOR_A, 0.5)]),
    )
    solicitud_id = _crear_solicitud()

    primera = client.post(f"/solicitudes/{solicitud_id}/busqueda")
    segunda = client.post(f"/solicitudes/{solicitud_id}/busqueda")

    assert primera.status_code == 200
    assert segunda.status_code == 409


def test_busqueda_acepta_estado_pendiente_en_minuscula(db_pruebas, monkeypatch):
    monkeypatch.setattr(
        clientes_m4, "buscar_candidatos",
        lambda *args, **kwargs: _respuesta_m4([_candidato(CONDUCTOR_A, 0.5)]),
    )
    solicitud_id = _crear_solicitud()
    solicitud = db_pruebas.get(Solicitud, solicitud_id)
    solicitud.estado = "pendiente"
    db_pruebas.commit()

    respuesta = client.post(f"/solicitudes/{solicitud_id}/busqueda")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "buscando"


# ── Cliente de M4 (respuestas HTTP simuladas) ───────────────────────────────

RESPUESTA_M4_OK = {
    "conductores": [_candidato(CONDUCTOR_A, 0.42)],
    "radio_aplicado_km": 5,
    "generado_en": "2026-11-22T21:00:00Z",
}


def _cliente_http(manejador):
    return httpx.Client(transport=httpx.MockTransport(manejador), base_url="http://m4")


def test_cliente_consulta_la_ruta_correcta_y_no_manda_destino():
    pedidos = []

    def manejador(request):
        pedidos.append(request)
        return httpx.Response(200, json=RESPUESTA_M4_OK)

    resultado = buscar_candidatos(
        -27.4512, -58.9866, "AUTO", cliente=_cliente_http(manejador), espera_seg=0
    )

    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert pedido.url.path == "/api/v1/conductores/cercanos"
    assert pedido.url.params["tipo_vehiculo"] == "AUTO"
    assert "origen_latitud" in pedido.url.params
    assert "origen_longitud" in pedido.url.params
    assert "destino_latitud" not in pedido.url.params
    assert "radio_km" not in pedido.url.params
    assert "x-request-id" in pedido.headers
    assert len(resultado.conductores) == 1


def test_cliente_lista_vacia_no_es_un_error():
    respuesta_vacia = {
        "conductores": [], "radio_aplicado_km": 9.5,
        "generado_en": "2026-11-22T21:00:00Z",
    }
    resultado = buscar_candidatos(
        -27.4512, -58.9866, "AUTO",
        cliente=_cliente_http(lambda request: httpx.Response(200, json=respuesta_vacia)),
        espera_seg=0,
    )
    assert resultado.conductores == []
    assert resultado.radio_aplicado_km == 9.5


def test_cliente_reintenta_y_falla_si_m4_sigue_caido():
    intentos = []

    def manejador(request):
        intentos.append(1)
        return httpx.Response(503)

    with pytest.raises(ErrorIntegracionM4):
        buscar_candidatos(
            -27.4512, -58.9866, "AUTO", cliente=_cliente_http(manejador), espera_seg=0
        )
    assert len(intentos) == 3


def test_cliente_se_recupera_si_m4_vuelve_en_el_segundo_intento():
    intentos = []

    def manejador(request):
        intentos.append(1)
        if len(intentos) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=RESPUESTA_M4_OK)

    resultado = buscar_candidatos(
        -27.4512, -58.9866, "AUTO", cliente=_cliente_http(manejador), espera_seg=0
    )
    assert len(intentos) == 2
    assert len(resultado.conductores) == 1


def test_cliente_timeout_es_un_error_no_una_lista_vacia():
    def manejador(request):
        raise httpx.ReadTimeout("M4 muy lento")

    with pytest.raises(ErrorIntegracionM4):
        buscar_candidatos(
            -27.4512, -58.9866, "AUTO", cliente=_cliente_http(manejador), espera_seg=0
        )


def test_cliente_error_400_no_se_reintenta():
    intentos = []

    def manejador(request):
        intentos.append(1)
        return httpx.Response(400)

    with pytest.raises(ErrorIntegracionM4):
        buscar_candidatos(
            -27.4512, -58.9866, "AUTO", cliente=_cliente_http(manejador), espera_seg=0
        )
    assert len(intentos) == 1


def test_cliente_respuesta_con_formato_invalido_es_un_error():
    with pytest.raises(ErrorIntegracionM4):
        buscar_candidatos(
            -27.4512, -58.9866, "AUTO",
            cliente=_cliente_http(lambda request: httpx.Response(200, json={"hola": 1})),
            espera_seg=0,
        )
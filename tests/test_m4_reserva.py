"""
Cliente de M4: reservar y liberar conductores (con respuestas HTTP simuladas)
"""
import json

import httpx
import pytest

from app.services.clientes_m4 import (
    ConflictoReservaM4,
    ErrorIntegracionM4,
    liberar_conductor,
    reservar_conductor,
)

CONDUCTOR_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SOLICITUD_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"


def _respuesta_m4(estado, idempotente=None):
    cuerpo = {
        "conductor_id": CONDUCTOR_ID,
        "solicitud_id": SOLICITUD_ID,
        "estado_temporal": estado,
        "actualizado_en": "2026-11-24T18:00:00Z",
    }
    if estado == "RESERVADO":
        cuerpo["expira_en"] = "2026-11-24T18:10:00Z"
    if idempotente is not None:
        cuerpo["idempotente"] = idempotente
    return cuerpo


def _cliente_http(manejador):
    return httpx.Client(transport=httpx.MockTransport(manejador), base_url="http://m4")


def test_reservar_envia_el_pedido_correcto():
    pedidos = []

    def manejador(request):
        pedidos.append(request)
        return httpx.Response(201, json=_respuesta_m4("RESERVADO"))

    resultado = reservar_conductor(
        CONDUCTOR_ID, SOLICITUD_ID, cliente=_cliente_http(manejador), espera_seg=0
    )

    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "POST"
    assert pedido.url.path == f"/api/v1/conductores/{CONDUCTOR_ID}/reserva"
    assert json.loads(pedido.content) == {
        "estado_temporal": "RESERVADO",
        "solicitud_id": SOLICITUD_ID,
    }
    assert pedido.headers["idempotency-key"]
    assert "x-request-id" in pedido.headers
    assert resultado.estado_temporal == "RESERVADO"
    assert resultado.expira_en is not None


def test_liberar_manda_solo_conductor_y_solicitud_sin_motivo():
    pedidos = []

    def manejador(request):
        pedidos.append(request)
        return httpx.Response(200, json=_respuesta_m4("LIBERADO"))

    resultado = liberar_conductor(
        CONDUCTOR_ID, SOLICITUD_ID, cliente=_cliente_http(manejador), espera_seg=0
    )

    pedido = pedidos[0]
    assert pedido.url.path == f"/api/v1/conductores/{CONDUCTOR_ID}/reserva"
    assert json.loads(pedido.content) == {
        "estado_temporal": "LIBERADO",
        "solicitud_id": SOLICITUD_ID,
    }
    assert resultado.estado_temporal == "LIBERADO"


def test_reservar_y_liberar_usan_claves_de_idempotencia_distintas():
    claves = []

    def manejador(request):
        claves.append(request.headers["idempotency-key"])
        estado = json.loads(request.content)["estado_temporal"]
        return httpx.Response(200, json=_respuesta_m4(estado))

    cliente = _cliente_http(manejador)
    reservar_conductor(CONDUCTOR_ID, SOLICITUD_ID, cliente=cliente, espera_seg=0)
    liberar_conductor(CONDUCTOR_ID, SOLICITUD_ID, cliente=cliente, espera_seg=0)

    assert len(claves) == 2
    assert claves[0] != claves[1]


def test_reservar_conductor_ya_reservado_da_conflicto_y_no_reintenta():
    intentos = []

    def manejador(request):
        intentos.append(1)
        return httpx.Response(409)

    with pytest.raises(ConflictoReservaM4):
        reservar_conductor(
            CONDUCTOR_ID, SOLICITUD_ID, cliente=_cliente_http(manejador), espera_seg=0
        )
    assert len(intentos) == 1


def test_reintento_usa_siempre_la_misma_clave_y_termina_en_error():
    claves = []

    def manejador(request):
        claves.append(request.headers["idempotency-key"])
        return httpx.Response(503)

    with pytest.raises(ErrorIntegracionM4):
        liberar_conductor(
            CONDUCTOR_ID, SOLICITUD_ID, cliente=_cliente_http(manejador), espera_seg=0
        )
    assert len(claves) == 3
    assert len(set(claves)) == 1


def test_liberacion_repetida_se_reconoce_como_idempotente():
    resultado = liberar_conductor(
        CONDUCTOR_ID, SOLICITUD_ID,
        cliente=_cliente_http(
            lambda request: httpx.Response(200, json=_respuesta_m4("LIBERADO", idempotente=True))
        ),
        espera_seg=0,
    )
    assert resultado.idempotente is True


def test_liberar_una_reserva_inexistente_da_error_sin_reintentar():
    intentos = []

    def manejador(request):
        intentos.append(1)
        return httpx.Response(404)

    with pytest.raises(ErrorIntegracionM4):
        liberar_conductor(
            CONDUCTOR_ID, SOLICITUD_ID, cliente=_cliente_http(manejador), espera_seg=0
        )
    assert len(intentos) == 1


def test_timeout_al_reservar_es_un_error():
    def manejador(request):
        raise httpx.ReadTimeout("M4 muy lento")

    with pytest.raises(ErrorIntegracionM4):
        reservar_conductor(
            CONDUCTOR_ID, SOLICITUD_ID, cliente=_cliente_http(manejador), espera_seg=0
        )
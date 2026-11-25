"""
RF-5.5 — Aceptar o rechazar ofertas
Endpoint: POST /ofertas/{oferta_id}/responder
Caller:   M3 (servicio), no el cliente.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud

client = TestClient(app)

CLIENTE_ID = "550e8400-e29b-41d4-a716-446655440000"
CONDUCTOR_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
CONDUCTOR_ID_OTRO = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


# ── Helpers ──────────────────────────────────────────────────────────────────

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


def _crear_oferta(solicitud_id, conductor_id=CONDUCTOR_ID):
    res = client.post("/ofertas/", json={
        "solicitud_id": solicitud_id,
        "conductor_id": conductor_id,
        "tiempo_expiracion_seg": 30,
    })
    assert res.status_code == 201
    return res.json()["oferta_id"]


def _setup(db_pruebas, conductor_id=CONDUCTOR_ID):
    """Crea solicitud + oferta. Pone la solicitud en `buscando` (despacho iniciado)."""
    solicitud_id = _crear_solicitud()
    sol = db_pruebas.get(Solicitud, solicitud_id)
    sol.estado = "buscando"
    db_pruebas.commit()
    oferta_id = _crear_oferta(solicitud_id, conductor_id)
    return solicitud_id, oferta_id


def _body(solicitud_id, oferta_id, respuesta, conductor_id=CONDUCTOR_ID):
    return {
        "solicitud_id": solicitud_id,
        "oferta_id": oferta_id,
        "conductor_id": conductor_id,
        "respuesta": respuesta,
    }


# ── Flujo feliz ───────────────────────────────────────────────────────────────

def test_aceptar_oferta(db_pruebas):
    """Aceptar una oferta asigna el conductor y devuelve repetida=false."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    res = client.post(
        f"/ofertas/{oferta_id}/responder",
        json=_body(solicitud_id, oferta_id, "aceptado"),
    )

    assert res.status_code == 200
    assert res.json() == {"repetida": False}

    oferta = db_pruebas.get(Oferta, oferta_id)
    db_pruebas.expire(oferta)
    oferta = db_pruebas.get(Oferta, oferta_id)
    assert oferta.estado == "aceptada"
    assert oferta.respondida_en is not None

    sol = db_pruebas.get(Solicitud, solicitud_id)
    db_pruebas.expire(sol)
    sol = db_pruebas.get(Solicitud, solicitud_id)
    assert sol.estado == "asignada"
    assert sol.conductor_id == CONDUCTOR_ID


def test_rechazar_oferta(db_pruebas):
    """Rechazar una oferta deja la solicitud en buscando y devuelve repetida=false."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    res = client.post(
        f"/ofertas/{oferta_id}/responder",
        json=_body(solicitud_id, oferta_id, "rechazado"),
    )

    assert res.status_code == 200
    assert res.json() == {"repetida": False}

    oferta = db_pruebas.get(Oferta, oferta_id)
    db_pruebas.expire(oferta)
    oferta = db_pruebas.get(Oferta, oferta_id)
    assert oferta.estado == "rechazada"

    sol = db_pruebas.get(Solicitud, solicitud_id)
    db_pruebas.expire(sol)
    sol = db_pruebas.get(Solicitud, solicitud_id)
    assert sol.estado == "buscando"
    assert sol.conductor_id is None


# ── Idempotencia ──────────────────────────────────────────────────────────────

def test_idempotencia_aceptar_dos_veces(db_pruebas):
    """Segunda aceptación idéntica devuelve repetida=true sin error."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    client.post(f"/ofertas/{oferta_id}/responder", json=_body(solicitud_id, oferta_id, "aceptado"))
    res = client.post(f"/ofertas/{oferta_id}/responder", json=_body(solicitud_id, oferta_id, "aceptado"))

    assert res.status_code == 200
    assert res.json() == {"repetida": True}


def test_idempotencia_rechazar_dos_veces(db_pruebas):
    """Segunda negativa idéntica devuelve repetida=true sin error."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    client.post(f"/ofertas/{oferta_id}/responder", json=_body(solicitud_id, oferta_id, "rechazado"))
    res = client.post(f"/ofertas/{oferta_id}/responder", json=_body(solicitud_id, oferta_id, "rechazado"))

    assert res.status_code == 200
    assert res.json() == {"repetida": True}


# ── Conflictos 409 ────────────────────────────────────────────────────────────

def test_409_ya_aceptada_conductor_intenta_rechazar(db_pruebas):
    """El conductor ganador intenta rechazar su propia oferta ya aceptada → 409 ya_aceptada."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    client.post(f"/ofertas/{oferta_id}/responder", json=_body(solicitud_id, oferta_id, "aceptado"))
    res = client.post(f"/ofertas/{oferta_id}/responder", json=_body(solicitud_id, oferta_id, "rechazado"))

    assert res.status_code == 409
    body = res.json()
    assert body["codigo"] == "solicitud_no_disponible"
    assert body["motivo"] == "ya_aceptada"


def test_409_ya_asignada_otro_conductor(db_pruebas):
    """Otro conductor intenta aceptar cuando la solicitud ya fue asignada → 409 ya_asignada."""
    solicitud_id, oferta_id_a = _setup(db_pruebas)

    oferta_id_b = _crear_oferta(solicitud_id, CONDUCTOR_ID_OTRO)

    client.post(f"/ofertas/{oferta_id_a}/responder", json=_body(solicitud_id, oferta_id_a, "aceptado"))

    res = client.post(
        f"/ofertas/{oferta_id_b}/responder",
        json=_body(solicitud_id, oferta_id_b, "aceptado", conductor_id=CONDUCTOR_ID_OTRO),
    )

    assert res.status_code == 409
    body = res.json()
    assert body["codigo"] == "solicitud_no_disponible"
    assert body["motivo"] == "ya_asignada"


def test_409_solicitud_cancelada(db_pruebas):
    """Responder a oferta cuando la solicitud fue cancelada → 409 solicitud_cancelada."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    client.post(f"/solicitudes/{solicitud_id}/cancelar", json={"cliente_id": CLIENTE_ID})

    res = client.post(
        f"/ofertas/{oferta_id}/responder",
        json=_body(solicitud_id, oferta_id, "aceptado"),
    )

    assert res.status_code == 409
    assert res.json()["motivo"] == "solicitud_cancelada"


# ── Vigencia 410 ──────────────────────────────────────────────────────────────

def test_410_oferta_expirada(db_pruebas):
    """Responder una oferta cuyo vence_en ya pasó → 410."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    oferta = db_pruebas.get(Oferta, oferta_id)
    oferta.vence_en = datetime.now(timezone.utc) - timedelta(seconds=60)
    db_pruebas.commit()

    res = client.post(
        f"/ofertas/{oferta_id}/responder",
        json=_body(solicitud_id, oferta_id, "aceptado"),
    )

    assert res.status_code == 410
    assert res.json()["codigo"] == "oferta_no_vigente"


# ── Validaciones 400/403/404/422 ──────────────────────────────────────────────

def test_404_oferta_no_existente(db_pruebas):
    res = client.post("/ofertas/id-inexistente/responder", json={
        "solicitud_id": "00000000-0000-0000-0000-000000000000",
        "oferta_id": "id-inexistente",
        "conductor_id": CONDUCTOR_ID,
        "respuesta": "aceptado",
    })
    assert res.status_code == 404


def test_403_conductor_no_es_destinatario(db_pruebas):
    """Conductor distinto al destinatario → 403."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    res = client.post(
        f"/ofertas/{oferta_id}/responder",
        json=_body(solicitud_id, oferta_id, "aceptado", conductor_id=CONDUCTOR_ID_OTRO),
    )
    assert res.status_code == 403


def test_400_oferta_id_no_coincide(db_pruebas):
    """oferta_id en URL distinto al del cuerpo → 400."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    res = client.post(
        f"/ofertas/{oferta_id}/responder",
        json=_body(solicitud_id, "otro-id-distinto", "aceptado"),
    )
    assert res.status_code == 400


def test_400_solicitud_id_no_coincide(db_pruebas):
    """solicitud_id del cuerpo no corresponde a la oferta → 400."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    res = client.post(
        f"/ofertas/{oferta_id}/responder",
        json=_body("00000000-0000-0000-0000-000000000099", oferta_id, "aceptado"),
    )
    assert res.status_code == 400


def test_422_respuesta_invalida(db_pruebas):
    """Valor de respuesta fuera del enum → 422."""
    solicitud_id, oferta_id = _setup(db_pruebas)

    res = client.post(
        f"/ofertas/{oferta_id}/responder",
        json=_body(solicitud_id, oferta_id, "IGNORAR"),
    )
    assert res.status_code == 422

"""
RF-5.6 — Asignación única con protección de concurrencia.
Usa POST /ofertas/{oferta_id}/responder (RF-5.5) como mecanismo de aceptación.
"""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.despacho import HistorialDespacho
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud


def crear_solicitud(client) -> tuple[str, str]:
    cliente_id = str(uuid4())
    r = client.post("/solicitudes", json={
        "cliente_id": cliente_id,
        "origen_latitud": -27.45,
        "origen_longitud": -58.98,
        "destino_latitud": -27.47,
        "destino_longitud": -58.83,
        "tipo_vehiculo": "AUTO",
    })
    assert r.status_code == 201
    return r.json()["solicitud_id"], cliente_id


def crear_oferta(client, solicitud_id: str, expiracion_seg: int = 600) -> dict:
    r = client.post("/ofertas/", json={
        "solicitud_id": solicitud_id,
        "conductor_id": str(uuid4()),
        "tiempo_expiracion_seg": expiracion_seg,
    })
    assert r.status_code == 201
    return r.json()


def responder(client, oferta: dict, respuesta: str):
    """Llama al nuevo endpoint RF-5.5 con la firma que espera M3."""
    return client.post(
        f"/ofertas/{oferta['oferta_id']}/responder",
        json={
            "solicitud_id": oferta["solicitud_id"],
            "oferta_id": oferta["oferta_id"],
            "conductor_id": oferta["conductor_id"],
            "respuesta": respuesta,
        },
    )


def test_asignacion_unica_con_aceptaciones_concurrentes(concurrencia_db):
    with TestClient(app) as client:
        solicitud_id, _ = crear_solicitud(client)
        ofertas = [crear_oferta(client, solicitud_id) for _ in range(10)]

    def aceptar(oferta):
        with TestClient(app) as c:
            return oferta, responder(c, oferta, "aceptado").status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        resultados = list(pool.map(aceptar, ofertas))

    codigos = [codigo for _, codigo in resultados]
    assert codigos.count(200) == 1
    assert codigos.count(409) == 9

    ganadora = next(o for o, codigo in resultados if codigo == 200)

    with concurrencia_db() as db:
        solicitud = db.get(Solicitud, solicitud_id)
        assert solicitud.estado == "asignada"
        assert solicitud.conductor_id == ganadora["conductor_id"]
        assert solicitud.fecha_asignacion is not None

        estados = [
            o.estado for o in
            db.query(Oferta).filter(Oferta.solicitud_id == solicitud_id)
        ]
        assert estados.count("aceptada") == 1
        assert estados.count("pendiente") == 9

        historial = db.query(HistorialDespacho).filter(
            HistorialDespacho.id_solicitud == solicitud_id
        ).all()
        assert len(historial) == 1


def test_segunda_aceptacion_secuencial_da_409(concurrencia_db):
    with TestClient(app) as client:
        solicitud_id, _ = crear_solicitud(client)
        o1 = crear_oferta(client, solicitud_id)
        o2 = crear_oferta(client, solicitud_id)

        assert responder(client, o1, "aceptado").status_code == 200
        assert responder(client, o2, "aceptado").status_code == 409


def test_oferta_inexistente_da_404(concurrencia_db):
    oferta_falsa = {
        "oferta_id": str(uuid4()),
        "solicitud_id": str(uuid4()),
        "conductor_id": str(uuid4()),
    }
    with TestClient(app) as client:
        assert responder(client, oferta_falsa, "aceptado").status_code == 404


def test_cliente_ajeno_da_403_y_no_asigna(concurrencia_db):
    with TestClient(app) as client:
        solicitud_id, _ = crear_solicitud(client)
        oferta = crear_oferta(client, solicitud_id)

        # Usar conductor_id distinto al de la oferta → 403
        oferta_con_conductor_ajeno = {**oferta, "conductor_id": str(uuid4())}
        r = responder(client, oferta_con_conductor_ajeno, "aceptado")
        assert r.status_code == 403

    with concurrencia_db() as db:
        assert db.get(Solicitud, solicitud_id).conductor_id is None


def test_oferta_expirada_da_410_y_no_asigna_la_solicitud(concurrencia_db):
    with TestClient(app) as client:
        solicitud_id, _ = crear_solicitud(client)
        oferta = crear_oferta(client, solicitud_id, expiracion_seg=-5)

        assert responder(client, oferta, "aceptado").status_code == 410

    with concurrencia_db() as db:
        solicitud = db.get(Solicitud, solicitud_id)
        assert solicitud.estado == "pendiente"
        assert solicitud.conductor_id is None


def test_rechazar_deja_la_solicitud_activa_y_permite_otra_oferta(concurrencia_db):
    with TestClient(app) as client:
        solicitud_id, _ = crear_solicitud(client)
        o1 = crear_oferta(client, solicitud_id)
        o2 = crear_oferta(client, solicitud_id)

        r = responder(client, o1, "rechazado")
        assert r.status_code == 200
        assert r.json() == {"repetida": False}

        # Oferta ya rechazada no se puede aceptar → 410 (no vigente)
        assert responder(client, o1, "aceptado").status_code == 410
        # La otra oferta sigue disponible
        assert responder(client, o2, "aceptado").status_code == 200

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


def crear_oferta(client, id_solicitud: str, expiracion_seg: int = 600) -> dict:
    r = client.post("/ofertas/", json={
        "id_solicitud": id_solicitud,
        "conductor_id": str(uuid4()),
        "tiempo_expiracion_seg": expiracion_seg,
    })
    assert r.status_code == 201
    return r.json()


def responder(client, id_oferta: str, cliente_id: str, accion: str):
    return client.patch(
        f"/ofertas/{id_oferta}/respuesta",
        json={"cliente_id": cliente_id, "accion": accion},
    )


def test_asignacion_unica_con_aceptaciones_concurrentes(concurrencia_db):
    with TestClient(app) as client:
        id_solicitud, cliente_id = crear_solicitud(client)
        ofertas = [crear_oferta(client, id_solicitud) for _ in range(10)]

    def aceptar(oferta):
        with TestClient(app) as c:  # un cliente por hilo
            return oferta, responder(c, oferta["id_oferta"], cliente_id, "ACEPTAR").status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        resultados = list(pool.map(aceptar, ofertas))

    codigos = [codigo for _, codigo in resultados]
    assert codigos.count(200) == 1
    assert codigos.count(409) == 9

    ganadora = next(o for o, codigo in resultados if codigo == 200)

    with concurrencia_db() as db:
        solicitud = db.get(Solicitud, id_solicitud)
        assert solicitud.estado == "ACEPTADA"
        assert solicitud.conductor_id == ganadora["conductor_id"]
        assert solicitud.fecha_asignacion is not None

        estados = [o.estado for o in db.query(Oferta).filter(Oferta.id_solicitud == id_solicitud)]
        assert estados.count("ACEPTADA") == 1
        assert estados.count("PENDIENTE") == 9

        historial = db.query(HistorialDespacho).filter(
            HistorialDespacho.id_solicitud == id_solicitud
        ).all()
        assert len(historial) == 1  # solo la aceptación ganadora deja registro


def test_segunda_aceptacion_secuencial_da_409(concurrencia_db):
    with TestClient(app) as client:
        id_solicitud, cliente_id = crear_solicitud(client)
        o1 = crear_oferta(client, id_solicitud)
        o2 = crear_oferta(client, id_solicitud)

        assert responder(client, o1["id_oferta"], cliente_id, "ACEPTAR").status_code == 200
        assert responder(client, o2["id_oferta"], cliente_id, "ACEPTAR").status_code == 409


def test_oferta_inexistente_da_404(concurrencia_db):
    with TestClient(app) as client:
        assert responder(client, str(uuid4()), str(uuid4()), "ACEPTAR").status_code == 404


def test_cliente_ajeno_da_403_y_no_asigna(concurrencia_db):
    with TestClient(app) as client:
        id_solicitud, _ = crear_solicitud(client)
        oferta = crear_oferta(client, id_solicitud)

        r = responder(client, oferta["id_oferta"], str(uuid4()), "ACEPTAR")
        assert r.status_code == 403

    with concurrencia_db() as db:
        assert db.get(Solicitud, id_solicitud).conductor_id is None


def test_oferta_expirada_da_409_y_no_asigna_la_solicitud(concurrencia_db):
    with TestClient(app) as client:
        id_solicitud, cliente_id = crear_solicitud(client)
        oferta = crear_oferta(client, id_solicitud, expiracion_seg=-5)

        assert responder(client, oferta["id_oferta"], cliente_id, "ACEPTAR").status_code == 409

    with concurrencia_db() as db:
        solicitud = db.get(Solicitud, id_solicitud)
        assert solicitud.estado == "PENDIENTE"
        assert solicitud.conductor_id is None


def test_rechazar_deja_la_solicitud_pendiente_y_permite_otra_oferta(concurrencia_db):
    with TestClient(app) as client:
        id_solicitud, cliente_id = crear_solicitud(client)
        o1 = crear_oferta(client, id_solicitud)
        o2 = crear_oferta(client, id_solicitud)

        r = responder(client, o1["id_oferta"], cliente_id, "RECHAZAR")
        assert r.status_code == 200
        assert r.json()["estado_oferta"] == "RECHAZADA"
        assert r.json()["estado_solicitud"] == "PENDIENTE"

        # una oferta ya respondida no se puede aceptar
        assert responder(client, o1["id_oferta"], cliente_id, "ACEPTAR").status_code == 409
        # la otra oferta sigue disponible
        assert responder(client, o2["id_oferta"], cliente_id, "ACEPTAR").status_code == 200
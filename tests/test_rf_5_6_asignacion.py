from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import obtener_db
from app.main import app
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud


@contextmanager
def sesion():
    """Sesión directa a la base para verificar el estado final."""
    gen = obtener_db()
    db = next(gen)
    try:
        yield db
    finally:
        gen.close()


def crear_solicitud(client) -> str:
    r = client.post("/solicitudes", json={
        "cliente_id": str(uuid4()),
        "origen_latitud": -27.45,
        "origen_longitud": -58.98,
        "destino_latitud": -27.47,
        "destino_longitud": -58.83,
        "tipo_vehiculo": "AUTO",
    })
    assert r.status_code == 201
    return r.json()["solicitud_id"]


def crear_oferta(client, id_solicitud: str, expiracion_seg: int = 600) -> dict:
    r = client.post("/ofertas/", json={
        "id_solicitud": id_solicitud,
        "conductor_id": str(uuid4()),
        "tiempo_expiracion_seg": expiracion_seg,
    })
    assert r.status_code == 201
    return r.json()


def test_asignacion_unica_con_aceptaciones_concurrentes():
    with TestClient(app) as client:
        id_solicitud = crear_solicitud(client)
        ofertas = [crear_oferta(client, id_solicitud) for _ in range(10)]

    def aceptar(oferta):
        # un cliente por hilo: TestClient no es seguro de compartir entre hilos
        with TestClient(app) as c:
            r = c.post(f"/ofertas/{oferta['id_oferta']}/aceptar")
            return oferta, r.status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        resultados = list(pool.map(aceptar, ofertas))

    codigos = [codigo for _, codigo in resultados]
    assert codigos.count(200) == 1
    assert codigos.count(409) == 9

    ganadora = next(o for o, codigo in resultados if codigo == 200)

    with sesion() as db:
        solicitud = db.get(Solicitud, id_solicitud)
        assert solicitud.estado == "ASIGNADA"
        assert solicitud.conductor_id == ganadora["conductor_id"]
        assert solicitud.fecha_asignacion is not None

        estados = [
            o.estado
            for o in db.query(Oferta).filter(Oferta.id_solicitud == id_solicitud)
        ]
        assert estados.count("ACEPTADA") == 1
        assert estados.count("CANCELADA") == 9


def test_segunda_aceptacion_secuencial_da_409():
    with TestClient(app) as client:
        id_solicitud = crear_solicitud(client)
        o1 = crear_oferta(client, id_solicitud)
        o2 = crear_oferta(client, id_solicitud)

        assert client.post(f"/ofertas/{o1['id_oferta']}/aceptar").status_code == 200
        assert client.post(f"/ofertas/{o2['id_oferta']}/aceptar").status_code == 409


def test_oferta_inexistente_da_404():
    with TestClient(app) as client:
        r = client.post(f"/ofertas/{uuid4()}/aceptar")
        assert r.status_code == 404


def test_oferta_expirada_da_409_y_no_asigna_la_solicitud():
    with TestClient(app) as client:
        id_solicitud = crear_solicitud(client)
        oferta = crear_oferta(client, id_solicitud, expiracion_seg=-5)

        r = client.post(f"/ofertas/{oferta['id_oferta']}/aceptar")
        assert r.status_code == 409

    with sesion() as db:
        solicitud = db.get(Solicitud, id_solicitud)
        assert solicitud.estado == "PENDIENTE"
        assert solicitud.conductor_id is None
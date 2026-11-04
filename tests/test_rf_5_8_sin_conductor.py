from datetime import datetime, timedelta, timezone
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


def crear_oferta(client, id_solicitud: str) -> dict:
    r = client.post("/ofertas/", json={
        "id_solicitud": id_solicitud,
        "conductor_id": str(uuid4()),
        "tiempo_expiracion_seg": 600,
    })
    assert r.status_code == 201
    return r.json()


def test_sin_candidatos_marca_sin_conductor(db_pruebas):
    client = TestClient(app)
    id_solicitud, _ = crear_solicitud(client)

    r = client.post(f"/solicitudes/{id_solicitud}/sin-conductor", json={"motivo": "SIN_CANDIDATOS"})

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "SIN_CONDUCTOR"
    assert cuerpo["motivo"] == "SIN_CANDIDATOS"
    assert cuerpo["ya_registrada"] is False

    db_pruebas.expire_all()
    assert db_pruebas.get(Solicitud, id_solicitud).estado == "SIN_CONDUCTOR"


def test_sin_cuerpo_usa_motivo_por_defecto(db_pruebas):
    client = TestClient(app)
    id_solicitud, _ = crear_solicitud(client)

    r = client.post(f"/solicitudes/{id_solicitud}/sin-conductor")

    assert r.status_code == 200
    assert r.json()["motivo"] == "SIN_CANDIDATOS"


def test_registra_historial_y_vence_ofertas_pendientes(db_pruebas):
    client = TestClient(app)
    id_solicitud, _ = crear_solicitud(client)
    crear_oferta(client, id_solicitud)
    crear_oferta(client, id_solicitud)

    r = client.post(f"/solicitudes/{id_solicitud}/sin-conductor")
    assert r.status_code == 200

    db_pruebas.expire_all()
    historial = db_pruebas.query(HistorialDespacho).filter(
        HistorialDespacho.id_solicitud == id_solicitud
    ).all()
    assert len(historial) == 1
    assert historial[0].estado_anterior == "PENDIENTE"
    assert historial[0].estado_nuevo == "SIN_CONDUCTOR"

    estados = [o.estado for o in db_pruebas.query(Oferta).filter(Oferta.id_solicitud == id_solicitud)]
    assert estados == ["EXPIRADA", "EXPIRADA"]


def test_repetir_la_notificacion_no_duplica(db_pruebas):
    client = TestClient(app)
    id_solicitud, _ = crear_solicitud(client)

    primera = client.post(f"/solicitudes/{id_solicitud}/sin-conductor")
    segunda = client.post(f"/solicitudes/{id_solicitud}/sin-conductor")

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["ya_registrada"] is True

    db_pruebas.expire_all()
    historial = db_pruebas.query(HistorialDespacho).filter(
        HistorialDespacho.id_solicitud == id_solicitud
    ).count()
    assert historial == 1


def test_solicitud_inexistente_da_404(db_pruebas):
    client = TestClient(app)

    r = client.post(f"/solicitudes/{uuid4()}/sin-conductor")

    assert r.status_code == 404


def test_motivo_invalido_da_422(db_pruebas):
    client = TestClient(app)
    id_solicitud, _ = crear_solicitud(client)

    r = client.post(f"/solicitudes/{id_solicitud}/sin-conductor", json={"motivo": "OTRO"})

    assert r.status_code == 422


def test_solicitud_cancelada_da_409_y_no_cambia(db_pruebas):
    client = TestClient(app)
    id_solicitud, cliente_id = crear_solicitud(client)
    r = client.post(f"/solicitudes/{id_solicitud}/cancelar", json={"cliente_id": cliente_id})
    assert r.status_code == 200

    r = client.post(f"/solicitudes/{id_solicitud}/sin-conductor")

    assert r.status_code == 409
    db_pruebas.expire_all()
    assert db_pruebas.get(Solicitud, id_solicitud).estado == "CANCELADA"


def test_solicitud_aceptada_da_409_y_conserva_conductor(db_pruebas):
    client = TestClient(app)
    id_solicitud, cliente_id = crear_solicitud(client)
    oferta = crear_oferta(client, id_solicitud)
    r = client.patch(
        f"/ofertas/{oferta['id_oferta']}/respuesta",
        json={"cliente_id": cliente_id, "accion": "ACEPTAR"},
    )
    assert r.status_code == 200

    r = client.post(f"/solicitudes/{id_solicitud}/sin-conductor")

    assert r.status_code == 409
    db_pruebas.expire_all()
    solicitud = db_pruebas.get(Solicitud, id_solicitud)
    assert solicitud.estado == "ACEPTADA"
    assert solicitud.conductor_id == oferta["conductor_id"]


def test_vencer_busquedas_solo_marca_las_que_pasaron_el_plazo(db_pruebas, monkeypatch):
    monkeypatch.setenv("BUSQUEDA_TIMEOUT_SEG", "120")
    client = TestClient(app)
    id_vieja, _ = crear_solicitud(client)
    id_reciente, _ = crear_solicitud(client)

    vieja = db_pruebas.get(Solicitud, id_vieja)
    vieja.fecha_creacion = datetime.now(timezone.utc) - timedelta(seconds=300)
    db_pruebas.commit()

    r = client.post("/solicitudes/vencer-busquedas")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["timeout_seg"] == 120
    assert cuerpo["cantidad"] == 1
    assert cuerpo["solicitudes"] == [id_vieja]

    db_pruebas.expire_all()
    assert db_pruebas.get(Solicitud, id_vieja).estado == "SIN_CONDUCTOR"
    assert db_pruebas.get(Solicitud, id_reciente).estado == "PENDIENTE"


def test_vencer_busquedas_no_toca_solicitudes_ya_asignadas(db_pruebas):
    client = TestClient(app)
    id_solicitud, cliente_id = crear_solicitud(client)
    oferta = crear_oferta(client, id_solicitud)
    client.patch(
        f"/ofertas/{oferta['id_oferta']}/respuesta",
        json={"cliente_id": cliente_id, "accion": "ACEPTAR"},
    )
    solicitud = db_pruebas.get(Solicitud, id_solicitud)
    solicitud.fecha_creacion = datetime.now(timezone.utc) - timedelta(seconds=9999)
    db_pruebas.commit()

    r = client.post("/solicitudes/vencer-busquedas")

    assert r.status_code == 200
    assert r.json()["cantidad"] == 0
    db_pruebas.expire_all()
    assert db_pruebas.get(Solicitud, id_solicitud).estado == "ACEPTADA"


def test_timeout_invalido_usa_valor_por_defecto(db_pruebas, monkeypatch):
    monkeypatch.setenv("BUSQUEDA_TIMEOUT_SEG", "abc")
    client = TestClient(app)

    r = client.post("/solicitudes/vencer-busquedas")

    assert r.status_code == 200
    assert r.json()["timeout_seg"] == 120

from uuid import UUID, uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import obtener_db
from app.main import app
from app.models.solicitud import Base, Solicitud

# Configuracion de SQLite en memoria aislado para este test
SQLITE_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLITE_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def inicializar_tablas():
    """Crea la tabla desde cero en cada test y la limpia al finalizar."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_pruebas():
    sesion = TestSessionLocal()
    app.dependency_overrides[obtener_db] = lambda: sesion
    try:
        yield sesion
    finally:
        app.dependency_overrides.pop(obtener_db, None)
        sesion.close()


client = TestClient(app)

# ── PRUEBAS RF 5.2 ─────────────────────────────────────────────────────────

RESERVA_ID = "11111111-1111-1111-1111-111111111111"
CLIENTE_ID = "550e8400-e29b-41d4-a716-446655440000"


def test_crear_solicitud_desde_reserva_exitosa(db_pruebas):
    datos = {
        "reserva_id": RESERVA_ID,
        "cliente_id": CLIENTE_ID,
        "origen_latitud": -27.4512,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "AUTO"
    }

    respuesta = client.post("/solicitudes/desde-reserva", json=datos)
    assert respuesta.status_code == 201

    resultado = respuesta.json()
    assert resultado["mensaje"] == "Solicitud desde reserva creada correctamente"
    assert resultado["estado"] == "PENDIENTE"
    assert resultado["reserva_id"] == RESERVA_ID

    solicitud_id = resultado["solicitud_id"]
    assert str(UUID(solicitud_id)) == solicitud_id

    # Verificacion directa en la BD en memoria
    solicitud_guardada = db_pruebas.get(Solicitud, solicitud_id)
    assert solicitud_guardada is not None
    assert solicitud_guardada.reserva_id == RESERVA_ID
    assert solicitud_guardada.cliente_id == CLIENTE_ID
    assert solicitud_guardada.estado == "PENDIENTE"


def test_evitar_solicitudes_duplicadas_misma_reserva(db_pruebas):
    reserva_id = str(uuid4())
    datos = {
        "reserva_id": reserva_id,
        "cliente_id": CLIENTE_ID,
        "origen_latitud": -27.4512,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "MOTO"
    }

    # Primer intento
    res1 = client.post("/solicitudes/desde-reserva", json=datos)
    assert res1.status_code == 201
    solicitud_id_1 = res1.json()["solicitud_id"]

    # Reintento (Idempotencia)
    res2 = client.post("/solicitudes/desde-reserva", json=datos)
    assert res2.status_code == 200
    solicitud_id_2 = res2.json()["solicitud_id"]

    # Debe ser la misma solicitud
    assert solicitud_id_1 == solicitud_id_2

    # Solo debe haber 1 fila en la BD
    cantidad = db_pruebas.query(Solicitud).filter(Solicitud.reserva_id == reserva_id).count()
    assert cantidad == 1


def test_rechazar_reserva_tipo_vehiculo_invalido():
    datos = {
        "reserva_id": str(uuid4()),
        "cliente_id": CLIENTE_ID,
        "origen_latitud": -27.4512,
        "origen_longitud": -58.9866,
        "destino_latitud": -27.4601,
        "destino_longitud": -58.9735,
        "tipo_vehiculo": "TRACTOR"
    }
    respuesta = client.post("/solicitudes/desde-reserva", json=datos)
    assert respuesta.status_code == 422          

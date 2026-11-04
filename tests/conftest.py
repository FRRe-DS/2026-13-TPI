import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import obtener_db
from app.main import app
from app.models.solicitud import Base

# Base de datos SQLite en memoria para tests aislados
SQLITE_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLITE_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def inicializar_tablas():
    """Crea todas las tablas antes de cada test y las elimina al finalizar."""
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


@pytest.fixture
def concurrencia_db(tmp_path):
    """Base SQLite en archivo: cada request usa su propia sesión y conexión."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrencia.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(bind=engine)
    SesionConcurrente = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def obtener_db_concurrente():
        sesion = SesionConcurrente()
        try:
            yield sesion
        finally:
            sesion.close()

    app.dependency_overrides[obtener_db] = obtener_db_concurrente
    try:
        yield SesionConcurrente
    finally:
        app.dependency_overrides.pop(obtener_db, None)
        engine.dispose()
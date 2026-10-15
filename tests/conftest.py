import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.database import obtener_db
from app.main import app
from app.models.solicitud import Base

load_dotenv()

TEST_DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("MYSQL_USER", "m5_user"),
    password=os.getenv("MYSQL_PASSWORD"),
    host="127.0.0.1",
    port=3307,
    database="m5_test_db"
)

test_engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(bind=test_engine)


@pytest.fixture
def db_pruebas():
    Base.metadata.create_all(bind=test_engine)

    conexion = test_engine.connect()
    transaccion = conexion.begin()
    sesion = TestSessionLocal(bind=conexion)

    def obtener_db_pruebas():
        yield sesion

    app.dependency_overrides[obtener_db] = obtener_db_pruebas

    try:
        yield sesion
    finally:
        app.dependency_overrides.pop(obtener_db, None)
        sesion.close()
        transaccion.rollback()
        conexion.close()
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("MYSQL_USER", "m5_user"),
    password=os.getenv("MYSQL_PASSWORD"),
    host=os.getenv("MYSQL_HOST", "127.0.0.1"),
    port=int(os.getenv("MYSQL_PORT", "3307")),
    database=os.getenv("MYSQL_DATABASE", "m5_db")
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)


def obtener_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
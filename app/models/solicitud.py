from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Solicitud(Base):
    __tablename__ = "solicitudes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origen: Mapped[str] = mapped_column(String(200))
    destino: Mapped[str] = mapped_column(String(200))
    tipo_vehiculo: Mapped[str] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(String(30), default="pendiente")
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
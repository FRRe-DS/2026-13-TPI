
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Solicitud(Base):
    __tablename__ = "solicitudes"

    solicitud_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    cliente_id: Mapped[str] = mapped_column(String(36), nullable=True)

    origen_latitud: Mapped[float] = mapped_column(Float)
    origen_longitud: Mapped[float] = mapped_column(Float)

    destino_latitud: Mapped[float] = mapped_column(Float)
    destino_longitud: Mapped[float] = mapped_column(Float)

    tipo_vehiculo: Mapped[str] = mapped_column(String(20))

    estado: Mapped[str] = mapped_column(
        String(30), default="PENDIENTE"
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    fecha_asignacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conductor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    fecha_asignacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


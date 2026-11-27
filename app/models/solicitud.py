from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Solicitud(Base):
    __tablename__ = "solicitudes"

    # Evita solicitudes inmediatas duplicadas para un mismo cliente.
    __table_args__ = (
        UniqueConstraint(
            "cliente_id",
            "idempotency_key",
            name="uq_cliente_idempotencia"
        ),
    )

    solicitud_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Idempotencia del RF-5.1 (solicitud inmediata).
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    # Guarda una huella de los datos originales de la petición.
    request_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    # Idempotencia del RF-5.2 (solicitud desde reserva).
    reserva_id: Mapped[str | None] = mapped_column(
        String(36), unique=True, nullable=True
    )

    cliente_id: Mapped[str] = mapped_column(
        String(36), nullable=True
    )

    # Correo del cliente utilizado para las notificaciones.
    cliente_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
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

    conductor_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
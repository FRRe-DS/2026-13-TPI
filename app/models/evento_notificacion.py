from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, DateTime, JSON, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.solicitud import Base


class EventoNotificacion(Base):

    __tablename__ = "eventos_notificacion"

    # Identificador único del evento para garantizar idempotencia.
    evento_id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid4())
    )

    # Solicitud asociada al evento.
    solicitud_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("solicitudes.solicitud_id"),
        nullable=False
    )

    tipo: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    # Cuerpo original enviado a M8.
    cuerpo: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )

    # Estado del envío del evento.
    estado: Mapped[str] = mapped_column(
        String(20), default="PENDIENTE"
    )

    intentos: Mapped[int] = mapped_column(
        Integer, default=0
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    fecha_envio: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Fecha a partir de la cual se puede reintentar el envío.
    proximo_intento: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
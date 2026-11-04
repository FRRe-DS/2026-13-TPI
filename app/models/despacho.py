from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.solicitud import Base

class HistorialDespacho(Base):
    __tablename__ = "historial_despacho"

    id_historial: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    id_solicitud: Mapped[str] = mapped_column(String(36), ForeignKey("solicitudes.solicitud_id"))
    # nullable=True porque el primer estado no tendrá un estado anterior
    estado_anterior: Mapped[str] = mapped_column(String(30), nullable=True) 
    estado_nuevo: Mapped[str] = mapped_column(String(30))
    fecha_cambio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
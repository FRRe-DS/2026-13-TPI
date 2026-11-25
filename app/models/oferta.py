import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.solicitud import Base

class Oferta(Base):
    __tablename__ = "ofertas"

    oferta_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    solicitud_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("solicitudes.solicitud_id"), nullable=False, index=True
    )
    conductor_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendiente"
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    vence_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    respondida_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.solicitud import Base

class Oferta(Base):
    __tablename__ = "ofertas"

    id_oferta: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # Se referencia a la primary key de la tabla solicitudes
    id_solicitud: Mapped[str] = mapped_column(String(36), ForeignKey("solicitudes.solicitud_id"))
    conductor_id: Mapped[str] = mapped_column(String(36))
    fecha_envio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_expiracion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(30))
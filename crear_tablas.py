from app.database import engine
from app.models.solicitud import Base, Solicitud
from app.models.oferta import Oferta
from app.models.despacho import HistorialDespacho
from app.models.evento_notificacion import EventoNotificacion

# Crea las tablas registradas en los modelos de SQLAlchemy.
Base.metadata.create_all(bind=engine)

print("Tablas creadas correctamente")
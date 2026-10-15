from app.database import engine
from app.models.solicitud import Base, Solicitud

Base.metadata.create_all(bind=engine)

print("Tablas creadas correctamente")
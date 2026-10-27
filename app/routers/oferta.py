from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models.oferta import Oferta
from app.schemas.oferta import OfertaCreate, OfertaResponse

router = APIRouter(prefix="/ofertas", tags=["Ofertas"])

@router.post("/", response_model=OfertaResponse, status_code=status.HTTP_201_CREATED)
def crear_oferta(oferta_in: OfertaCreate, db: Session = Depends(obtener_db)):
    ahora = datetime.now(timezone.utc)
    
    # Se usa tiempo_expiracion_seg del schema para calcular la fecha de expiración real
    expiracion = ahora + timedelta(seconds=oferta_in.tiempo_expiracion_seg)

    nueva_oferta = Oferta(
        id_solicitud=oferta_in.id_solicitud,
        conductor_id=oferta_in.conductor_id,
        fecha_envio=ahora,
        fecha_expiracion=expiracion,  # Se asigna a la columna de la base de datos
        estado="PENDIENTE"
    )

    db.add(nueva_oferta)
    db.commit()
    db.refresh(nueva_oferta)

    return nueva_oferta
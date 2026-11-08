from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import update

from app.database import obtener_db
from app.models.oferta import Oferta
from app.schemas.oferta import OfertaCreate, OfertaResponse, RespuestaOferta
from app.services.asignacion import asignar_conductor, rechazar_oferta

router = APIRouter(prefix="/ofertas", tags=["Ofertas"])

@router.post("/", response_model=OfertaResponse, status_code=status.HTTP_201_CREATED)
def crear_oferta(oferta_in: OfertaCreate, db: Session = Depends(obtener_db)):
    ahora = datetime.now(timezone.utc)
    
    expiracion = ahora + timedelta(seconds=oferta_in.tiempo_expiracion_seg)

    nueva_oferta = Oferta(
        id_solicitud=oferta_in.id_solicitud,
        conductor_id=oferta_in.conductor_id,
        fecha_envio=ahora,
        fecha_expiracion=expiracion,
        estado="PENDIENTE"
    )

    db.add(nueva_oferta)
    db.commit()
    db.refresh(nueva_oferta)

    return nueva_oferta

@router.patch("/{id_oferta}/respuesta")
def responder_oferta(
    id_oferta: str, datos: RespuestaOferta, db: Session = Depends(obtener_db)
):
    oferta = db.get(Oferta, id_oferta)
    if oferta is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")

    if oferta.conductor_id != str(datos.conductor_id):
        raise HTTPException(
            status_code=403, detail="El conductor no es el destinatario de esta oferta"
        )

    if datos.accion == "ACEPTAR":
        return asignar_conductor(db, id_oferta)
    return rechazar_oferta(db, id_oferta)

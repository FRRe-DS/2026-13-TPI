from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import update
from app.models.solicitud import Solicitud

from app.database import obtener_db
from app.models.oferta import Oferta
from app.schemas.oferta import OfertaCreate, OfertaResponse, RespuestaOferta
from app.services.asignacion import asignar_conductor, rechazar_oferta

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

@router.patch("/{id_oferta}/respuesta")
def responder_oferta(
    id_oferta: str, datos: RespuestaOferta, db: Session = Depends(obtener_db)
):
    oferta = db.get(Oferta, id_oferta)
    if oferta is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")

    solicitud = db.get(Solicitud, oferta.id_solicitud)
    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if solicitud.cliente_id != str(datos.cliente_id):
        raise HTTPException(
            status_code=403, detail="El cliente no es el dueño de la solicitud"
        )

    if datos.accion == "ACEPTAR":
        return asignar_conductor(db, id_oferta)
    return rechazar_oferta(db, id_oferta)
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import update
from app.models.solicitud import Solicitud

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

@router.post("/{id_oferta}/aceptar")
def aceptar_oferta(id_oferta: str, db: Session = Depends(obtener_db)):
    ahora = datetime.now(timezone.utc)

    oferta = db.get(Oferta, id_oferta)
    if oferta is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")

    id_solicitud = oferta.id_solicitud
    conductor_id = oferta.conductor_id

    r_solicitud = db.execute(
        update(Solicitud)
        .where(
            Solicitud.solicitud_id == id_solicitud,
            Solicitud.estado == "PENDIENTE",
            Solicitud.conductor_id.is_(None),
        )
        .values(
            conductor_id=conductor_id,
            estado="ASIGNADA",
            fecha_asignacion=ahora,
        )
        .execution_options(synchronize_session=False)
    )
    if r_solicitud.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="La solicitud ya fue asignada a otro conductor",
        )

    r_oferta = db.execute(
        update(Oferta)
        .where(
            Oferta.id_oferta == id_oferta,
            Oferta.estado == "PENDIENTE",
            Oferta.fecha_expiracion > ahora,
        )
        .values(estado="ACEPTADA")
        .execution_options(synchronize_session=False)
    )
    if r_oferta.rowcount != 1:
        db.rollback()  
        raise HTTPException(
            status_code=409,
            detail="La oferta ya fue respondida o expiró",
        )

    db.execute(
        update(Oferta)
        .where(
            Oferta.id_solicitud == id_solicitud,
            Oferta.estado == "PENDIENTE",
        )
        .values(estado="CANCELADA")
        .execution_options(synchronize_session=False)
    )

    db.commit()

    return {
        "id_oferta": id_oferta,
        "id_solicitud": id_solicitud,
        "conductor_id": conductor_id,
        "estado": "ASIGNADA",
    }
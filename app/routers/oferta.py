from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud
from app.schemas.oferta import EstadoOferta, OfertaResponse
from app.services.ofertas_service import procesar_ofertas_vencidas

router = APIRouter(tags=["Ofertas"])


@router.get(
    "/solicitudes/{solicitud_id}/ofertas",
    response_model=List[OfertaResponse],
    summary="Consultar ofertas de una solicitud",
)
def listar_ofertas_solicitud(
    solicitud_id: UUID,
    db: Session = Depends(obtener_db),
):
    solicitud = (
        db.query(Solicitud)
        .filter(Solicitud.solicitud_id == str(solicitud_id))
        .first()
    )
    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada",
        )

    procesar_ofertas_vencidas(db)

    return (
        db.query(Oferta)
        .filter(Oferta.solicitud_id == str(solicitud_id))
        .order_by(Oferta.creada_en.asc())
        .all()
    )


@router.get(
    "/conductores/{conductor_id}/ofertas",
    response_model=List[OfertaResponse],
    summary="Consultar ofertas de un conductor",
)
def listar_ofertas_conductor(
    conductor_id: UUID,
    estado: Optional[EstadoOferta] = Query(
        default=None, description="Filtra por el estado de la oferta."
    ),
    db: Session = Depends(obtener_db),
):
    procesar_ofertas_vencidas(db)

    query = db.query(Oferta).filter(Oferta.conductor_id == str(conductor_id))
    if estado is not None:
        query = query.filter(Oferta.estado == estado.value)

    return query.order_by(Oferta.creada_en.desc()).all()
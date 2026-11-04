from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models.solicitud import Solicitud
#from app.models.oferta import Oferta
from app.servicios import registrar_cambio_estado  # O el nombre del archivo de servicios que está en /app

router = APIRouter(prefix="/solicitudes", tags=["Despacho y Trazabilidad"])

@router.patch("/{solicitud_id}/cancelar", status_code=status.HTTP_200_OK)
def cancelar_solicitud(solicitud_id: str, db: Session = Depends(obtener_db)):
    """
    Permite al cliente cancelar una solicitud antes de que sea asignada.
    Registra el evento de cancelación en el historial de despacho (RF-5.9).
    """
    solicitud = db.get(Solicitud, solicitud_id)
    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada"
        )

    # Validar si se puede cancelar (por ejemplo, si está pendiente o buscando)
    if solicitud.estado not in ["PENDIENTE", "BUSCANDO_CANDIDATOS", "OFERTADA"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede cancelar una solicitud en estado {solicitud.estado}"
        )

    # Actualizamos el estado utilizando nuestra función de trazabilidad
    solicitud_actualizada = registrar_cambio_estado(db, solicitud_id, "CANCELADA")

    return {
        "mensaje": "Solicitud cancelada correctamente",
        "solicitud_id": solicitud_id,
        "estado": solicitud_actualizada.estado
    }


@router.post("/{solicitud_id}/buscar", status_code=status.HTTP_200_OK)
def iniciar_busqueda(solicitud_id: str, db: Session = Depends(obtener_db)):
    solicitud = db.get(Solicitud, solicitud_id)
    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada"
        )

    if solicitud.estado != "PENDIENTE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede iniciar búsqueda desde el estado {solicitud.estado}"
        )

    solicitud_actualizada = registrar_cambio_estado(db, solicitud_id, "BUSCANDO_CANDIDATOS")

    return {
        "mensaje": "Búsqueda de conductores iniciada",
        "solicitud_id": solicitud_id,
        "estado": solicitud_actualizada.estado
    }
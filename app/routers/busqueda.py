from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.schemas.busqueda import RespuestaBusqueda
from app.services.busqueda import iniciar_busqueda

router = APIRouter(prefix="/solicitudes", tags=["Búsqueda de candidatos"])


@router.post(
    "/{solicitud_id}/busqueda",
    response_model=RespuestaBusqueda,
    status_code=status.HTTP_200_OK,
    summary="Búsqueda de candidatos (RF-5.3)",
)
def buscar_candidatos_de_solicitud(
    solicitud_id: UUID,
    db: Session = Depends(obtener_db),
):
    return iniciar_busqueda(db, str(solicitud_id))
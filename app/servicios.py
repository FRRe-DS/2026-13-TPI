from sqlalchemy.orm import Session
from app.models.despacho import HistorialDespacho
from app.models.solicitud import Solicitud

def registrar_cambio_estado(db: Session, solicitud_id: str, nuevo_estado: str):
    """
    Actualiza el estado de una solicitud y registra el cambio en el historial de despacho.
    """
    solicitud = db.get(Solicitud, solicitud_id)
    if not solicitud:
        return None

    estado_anterior = solicitud.estado
    
    # Si el estado es exactamente el mismo, no duplicamos historial
    if estado_anterior == nuevo_estado:
        return solicitud

    # Actualizamos el estado actual de la solicitud
    solicitud.estado = nuevo_estado

    # Creamos el registro en el historial de despacho
    historial = HistorialDespacho(
        id_solicitud=solicitud_id,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado
    )
    
    db.add(historial)
    db.commit()
    db.refresh(solicitud)
    
    return solicitud
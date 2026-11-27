import os
import httpx

from fastapi import HTTPException
from uuid import UUID

# Dirección base del módulo M2.
M2_URL = os.getenv("M2_URL")

def validar_estado_cuenta(cliente_id: UUID, token_servicio: str):
    # Verifica que la dirección de M2 esté configurada.
    if not M2_URL:
        raise HTTPException(503, "M2 no configurado")

    # Consulta el estado de cuenta utilizando el token de servicio.
    try:
        respuesta = httpx.get(
            f"{M2_URL}/api/v1/clientes/{cliente_id}/estado-cuenta",
            headers={"Authorization": f"Bearer {token_servicio}"},
            timeout=5.0
        )
    except httpx.RequestError:
        raise HTTPException(503, "M2 no disponible")

    # Verifica que el cliente exista.
    if respuesta.status_code == 404:
        raise HTTPException(422, "Cliente inexistente")

    if respuesta.status_code != 200:
        raise HTTPException(503, "Error al consultar M2")

    # Valida que M2 devuelva una respuesta válida.
    try:
        estado = respuesta.json().get("estado")
    except (ValueError, AttributeError):
        raise HTTPException(503, "Respuesta inválida de M2")

    if estado == "BLOQUEADO":
        raise HTTPException(422, "Cliente no activo")

    if estado != "ACTIVO":
        raise HTTPException(503, "Estado de cuenta inválido en M2")
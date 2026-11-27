import os
import httpx
import math

from fastapi import HTTPException

# Dirección del módulo de Ubicación y Disponibilidad.
M4_URL = os.getenv("M4_URL")

# Dirección del módulo de Tarifas, Pagos y Liquidaciones.
M7_URL = os.getenv("M7_URL")

def consultar_distancia(origen_latitud, origen_longitud,
                       destino_latitud, destino_longitud,
                       token_servicio):

    # Verifica que M4 esté configurado.
    if not M4_URL:
        raise HTTPException(503, "M4 no configurado")

    # Solicita la estimación del trayecto a M4.
    try:
        respuesta = httpx.get(
            f"{M4_URL}/api/v1/rutas/estimacion",
            params={
                "origen_latitud": origen_latitud,
                "origen_longitud": origen_longitud,
                "destino_latitud": destino_latitud,
                "destino_longitud": destino_longitud
            },
            headers={"Authorization": f"Bearer {token_servicio}"},
            timeout=5.0
        )

        respuesta.raise_for_status()
        return respuesta.json()

    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Error al consultar M4")

def consultar_tarifa(tipo_vehiculo, distancia_km,
                     duracion_min, token_servicio):

    # Verifica que M7 esté configurado.
    if not M7_URL:
        raise HTTPException(503, "M7 no configurado")

    # Solicita el cálculo de la tarifa estimada a M7.
    try:
        respuesta = httpx.post(
            f"{M7_URL}/api/v1/tarifas/estimaciones",
            json={
                "tipo_vehiculo": tipo_vehiculo.lower(),
                "distancia_km": distancia_km,
                "duracion_estimada_min": math.ceil(duracion_min)
            },
            headers={"Authorization": f"Bearer {token_servicio}"},
            timeout=5.0
        )

        respuesta.raise_for_status()
        return respuesta.json()

    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Error al consultar M7")
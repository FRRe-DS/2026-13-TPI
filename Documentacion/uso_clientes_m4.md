# Cómo usar el cliente de M4 (`app/services/clientes_m4.py`)

Este archivo contiene las funciones que M5 usa para hablar con M4 (conductores).
Están listas y probadas (`tests/test_rf_5_3.py` y `tests/test_m4_reserva.py`).
**Cada requisito solo tiene que importarlas y llamarlas.** No hace falta programar
nada de la comunicación con M4.

Contrato de referencia: `openapiM4.yml` y "Contrato M4-M5" (versión de noviembre 2026).

## Resumen

| Función | Para qué sirve | La usa |
|---|---|---|
| `buscar_candidatos(...)` | Pide a M4 la lista de conductores cercanos. No reserva a nadie. | RF-5.3 (ya hecho) |
| `reservar_conductor(conductor_id, solicitud_id)` | Reserva a UN conductor para una solicitud (M4 lo bloquea 10 minutos). | RF-5.4 |
| `liberar_conductor(conductor_id, solicitud_id)` | Libera la reserva de UN conductor. | RF-5.5, RF-5.6, RF-5.7, oferta vencida |

Reparto sugerido (a confirmar por el grupo).

## Cómo importarlas

```python
from app.services.clientes_m4 import (
    reservar_conductor,
    liberar_conductor,
    ConflictoReservaM4,
    ErrorIntegracionM4,
)
```

## Reservar un conductor

```python
try:
    reservar_conductor(conductor_id, solicitud_id)
except ConflictoReservaM4:
    # Otra solicitud ya tiene a ese conductor: pasar al siguiente de la lista.
    ...
except ErrorIntegracionM4:
    # M4 no respondió (ya se reintentó 3 veces). NO es "sin conductores".
    ...
```

- Se reserva de a UN conductor por llamada. Para un lote, se llama una vez por conductor.
- Si M4 responde 409, se lanza `ConflictoReservaM4`. En un lote hay que atraparlo
  por cada conductor y seguir con los demás.
- Devuelve un objeto con `estado_temporal` ("RESERVADO") y `expira_en` (10 minutos).

## Liberar un conductor

```python
liberar_conductor(conductor_id, solicitud_id)
```

- El mensaje es el mismo sin importar el motivo (rechazo, vencimiento, cancelación...).
- Repetir la liberación es seguro: M4 no hace nada de más.
- Al aceptar un conductor, hay que liberar a los demás que habían quedado reservados.
- Si M4 responde 404 (esa reserva nunca existió) se lanza `ErrorIntegracionM4`.

## Errores

| Error | Cuándo ocurre | Qué hacer |
|---|---|---|
| `ConflictoReservaM4` | M4 respondió 409 (conductor ya reservado por otra solicitud, o la solicitud no coincide al liberar). | Al reservar: pasar al siguiente conductor. |
| `ErrorIntegracionM4` | Timeout, M4 caído, 5xx tras 3 intentos, 404, respuesta inválida. | Registrar el error y decidir si reintentar más tarde. Nunca tratarlo como "lista vacía". |

## Claves de idempotencia

M4 exige el header `Idempotency-Key`. Las funciones lo generan solas:

- Reservar: `reserva-{solicitud_id}-{conductor_id}`
- Liberar: `liberacion-{solicitud_id}-{conductor_id}`

Reservar y liberar usan claves distintas, como pide M4. Si hay que reservar OTRA VEZ al
mismo conductor para la misma solicitud (por ejemplo, rechazó y se lo vuelven a ofrecer),
conviene pasar una clave propia:

```python
reservar_conductor(conductor_id, solicitud_id, idempotency_key="reserva-2-...")
```

## Reintentos y tiempos

- Reintenta hasta 3 veces ante timeout, falta de conexión o HTTP 429/500/502/503/504,
  con la misma clave de idempotencia.
- No reintenta ante 409, 404 u otros errores.

## Configuración (variables de entorno)

| Variable | Para qué | Valor por defecto |
|---|---|---|
| `M4_BASE_URL` | Dirección de M4 | `http://localhost:8004` (provisorio, falta la real) |
| `M4_TIMEOUT_SEG` | Tiempo máximo de espera | `3` |
| `M4_TOKEN` | Token JWT de M1 (opcional) | sin token |

## Estado actual

- `reservar_conductor` y `liberar_conductor` todavía NO están conectadas a ningún flujo.
- Probadas solo con respuestas simuladas de M4, no contra el M4 real.
- Modelo de envío de ofertas (de a uno o por lotes) lo define el RF-5.4; estas funciones
  sirven para ambos.
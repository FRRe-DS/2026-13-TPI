# Catálogo de eventos — M5: Solicitud y Despacho

## 1. Objetivo

Este documento identifica los eventos relevantes para la comunicación del módulo M5 con otros servicios de la plataforma de movilidad urbana.

Los eventos se presentan como una propuesta inicial de integración. Su publicación, consumo y transporte todavía no están implementados.

## 2. Eventos propuestos

| Evento | Emisor | Consumidor previsto | Descripción |
|---|---|---|---|
| `solicitud.creada` | M5 | Por definir | Se registra correctamente una nueva solicitud de viaje. |
| `reserva.activada` | M9 | M5 | Una reserva alcanza el momento de activación y requiere iniciar el despacho. |
| `conductor.asignado` | M5 | M6, M8 | Se confirma la asignación de un conductor a una solicitud. |
| `solicitud.sin_conductor` | M5 | M9, M8, según corresponda | Finaliza la búsqueda sin encontrar un conductor adecuado. |
| `solicitud.cancelada` | M5 | Por definir | Se cancela una solicitud antes de completar su asignación. |

Los nombres y consumidores de estos eventos deberán coordinarse con los equipos correspondientes.

## 3. Información mínima propuesta

Los eventos deberían contener:

- `evento_id`: identificador UUID del evento.
- `tipo_evento`: nombre del evento.
- `fecha_evento`: fecha y hora de generación.
- `solicitud_id`: identificador de la solicitud, cuando corresponda.
- `datos`: información específica del evento.

Por ejemplo, un evento de solicitud creada podría representarse así:

```json
{
  "evento_id": "c6c75f61-26a1-42cb-a0a7-928a84e59d5e",
  "tipo_evento": "solicitud.creada",
  "fecha_evento": "2026-10-17T18:00:00Z",
  "solicitud_id": "550e8400-e29b-41d4-a716-446655440000",
  "datos": {
    "cliente_id": "a3e4d8c2-75b1-4f92-8b12-456789abcdef",
    "estado": "PENDIENTE"
  }
}
```

## 4. Consideraciones de integración

- Cada módulo será responsable de los eventos que publique.
- Los consumidores deberán interpretar los eventos según los contratos acordados.
- Las operaciones críticas deberán diseñarse para evitar efectos duplicados ante reintentos.
- Los eventos no deberán incluir datos sensibles innecesarios.
- La comunicación asíncrona se implementará en una etapa posterior, de acuerdo con los requisitos del TPI.

## 5. Estado actual

**Documentación inicial — TP1.**

El catálogo contiene eventos propuestos para la evolución del módulo M5.

Actualmente no se publican ni consumen eventos mediante un sistema de mensajería.

La definición definitiva de nombres, estructuras, destinatarios y mecanismos de entrega queda pendiente de coordinación entre los equipos.
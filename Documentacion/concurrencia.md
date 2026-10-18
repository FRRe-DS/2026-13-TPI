# Estrategia de concurrencia — M5

## Objetivo

Evitar que un mismo conductor sea asignado simultáneamente a más de una solicitud de viaje activa.

## Problema identificado

Dos o más solicitudes podrían intentar asignar al mismo conductor de forma concurrente. Una simple consulta de disponibilidad no es suficiente, porque el estado del conductor podría cambiar antes de confirmar la asignación.

## Estrategia propuesta

1. M5 consulta los conductores candidatos mediante M4.
2. M5 verifica la habilitación y los datos del conductor mediante M3.
3. Antes de confirmar una asignación, M5 solicita a M4 un bloqueo temporal del conductor.
4. M5 registra la asignación mediante una operación transaccional en su propia base de datos.
5. La base de datos deberá aplicar una restricción de unicidad adecuada para impedir asignaciones activas duplicadas.
6. Si existe un conflicto, M5 rechaza la asignación y podrá evaluar otro conductor.

El mecanismo definitivo de bloqueo, su duración, liberación y recuperación ante fallos deberán acordarse con M4.

## Consideraciones

- Consultar disponibilidad y confirmar una asignación son operaciones diferentes.
- El control de concurrencia no debe depender únicamente de verificaciones realizadas en memoria.
- Los conflictos deben producir respuestas explícitas y controladas.
- La coordinación con M4 no reemplaza las garantías transaccionales que corresponden a M5.

## Estado de implementación

**TP1 — Estrategia documentada, implementación pendiente.**

Actualmente M5 permite crear y persistir solicitudes de viaje, pero todavía no realiza asignaciones de conductores.

Por lo tanto, este documento describe una solución propuesta y no constituye una garantía de concurrencia ya implementada.

El alcance de implementación exigido para RNF-08 en TP1 deberá confirmarse con la cátedra.
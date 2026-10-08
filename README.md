# Desarrollo de Software 2026 — TPI

## Grupo 13 — M5: Solicitud y Despacho

### Descripción del proyecto

Este repositorio corresponde al **Trabajo Práctico Integrador (TPI)** de la asignatura Desarrollo de Software — 2026.

El proyecto consiste en desarrollar una **plataforma distribuida de movilidad urbana bajo demanda**, que permita conectar clientes que solicitan viajes con conductores habilitados para prestar servicios de transporte en auto o moto.

Nuestro grupo tiene asignado el **Módulo M5 — Solicitud y Despacho**, responsable de gestionar solicitudes de viaje, buscar conductores disponibles, enviar ofertas y garantizar la asignación de un único conductor por solicitud.

### Integrantes — Grupo 13

1. Barberan, Facundo
2. Bassi, Ayelen
3. Escalante, Alejo
4. Franco, Ivan
5. Lopez, Agustin
6. Mendez, Joaquin
7. Quiroz, Ariel
8. Samardich, Agustin
9. Servin, Santiago

### Tecnologías previstas

| Tecnología | Propósito |
|---|---|
| Python | Lenguaje de programación |
| FastAPI | Framework para desarrollar la API |
| SQLAlchemy | Acceso y persistencia de datos mediante ORM |
| PostgreSQL | Base de datos relacional |
| Docker | Contenerización del servicio |
| OpenAPI / Swagger | Documentación y pruebas de endpoints |
| Git y GitHub | Control de versiones y trabajo colaborativo |

**Nota:** Las tecnologías podrán ajustarse según las necesidades del proyecto y las decisiones del equipo.

### Requerimientos funcionales — M5

| ID | Requerimiento |
|---|---|
| RF-5.1 | Solicitud de viaje inmediato |
| RF-5.2 | Solicitud desde reserva |
| RF-5.3 | Búsqueda de candidatos |
| RF-5.4 | Oferta con vencimiento |
| RF-5.5 | Aceptar o rechazar ofertas |
| RF-5.6 | Asignación única |
| RF-5.7 | Cancelación previa |
| RF-5.8 | Sin disponibilidad |
| RF-5.9 | Trazabilidad del despacho |

### Integración con otros módulos

El módulo M5 deberá comunicarse con los siguientes servicios:

- **M2 — Clientes:** información del cliente.
- **M3 — Conductores y Vehículos:** habilitación de conductores y vehículos.
- **M4 — Ubicación y Disponibilidad:** búsqueda de conductores cercanos y disponibles.
- **M6 — Viajes y Ciclo de Vida:** coordinación de la asignación y el inicio del ciclo del viaje.
- **M9 — Reservas de Viajes:** activación de solicitudes provenientes de reservas.

La integración entre módulos se realizará mediante APIs y eventos, respetando la independencia y propiedad de los datos de cada servicio.

### Estado del proyecto

**En desarrollo — Etapa inicial.**

Actualmente el equipo se encuentra trabajando en el análisis de requerimientos, la definición de tecnologías y la organización del repositorio.

---

**Asignatura:** Desarrollo de Software  
**Año:** 2026  
**Grupo:** 13  
**Módulo asignado:** M5 — Solicitud y Despacho
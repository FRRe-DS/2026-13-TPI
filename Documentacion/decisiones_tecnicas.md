# Decisiones técnicas — M5: Solicitud y Despacho

## 1. Objetivo

Este documento presenta las decisiones tecnológicas adoptadas por el Grupo 13 para desarrollar el módulo M5 — Solicitud y Despacho, correspondiente al Trabajo Práctico Integrador de Desarrollo de Software 2026.

Las tecnologías fueron seleccionadas considerando la simplicidad de desarrollo, la organización del código, la persistencia de datos y la posibilidad de integración con otros módulos mediante APIs.

## 2. Lenguaje de programación: Python 3.10

Se seleccionó **Python** por su sintaxis clara, facilidad de mantenimiento y disponibilidad de bibliotecas para desarrollar aplicaciones web.

Su utilización permite organizar la lógica del módulo y facilita la incorporación progresiva de nuevas funcionalidades.

## 3. Framework: FastAPI

Se seleccionó **FastAPI** para implementar la API REST del módulo M5.

Entre sus principales ventajas se encuentran:

- Definición sencilla de endpoints HTTP.
- Validación automática de los datos recibidos.
- Generación de documentación interactiva mediante OpenAPI y Swagger.
- Integración con bibliotecas de acceso a bases de datos.
- Compatibilidad con pruebas automatizadas.

FastAPI permite definir contratos de comunicación claros, necesarios para la integración con los demás módulos del sistema.

## 4. Persistencia: MySQL y SQLAlchemy

Se seleccionó **MySQL 8.4** como sistema de gestión de bases de datos relacional.

El módulo M5 necesita almacenar solicitudes de viaje, sus identificadores, coordenadas, estados y fechas de creación.

Para acceder a la base de datos se utiliza **SQLAlchemy**, que permite representar las tablas mediante clases de Python y realizar operaciones de persistencia utilizando un ORM.

Esta combinación facilita la organización del código y mantiene separadas las responsabilidades de la API y del acceso a datos.

## 5. Contenedores: Docker y Docker Compose

Se seleccionó **Docker** para ejecutar la aplicación y sus dependencias en entornos reproducibles.

Mediante **Docker Compose** se administran dos servicios:

- **API M5:** aplicación desarrollada con FastAPI.
- **MySQL:** base de datos propia del módulo.

La configuración permite iniciar ambos servicios mediante un único comando, sin requerir una instalación local de MySQL.

## 6. Pruebas automatizadas: pytest

Se utiliza **pytest** junto con las herramientas de prueba de FastAPI y HTTPX.

Las pruebas permiten verificar el funcionamiento de los endpoints y comprobar que las solicitudes se almacenan correctamente.

Para las pruebas de integración se utiliza una base de datos independiente, evitando modificar los datos del entorno principal.

## 7. Independencia del módulo

El módulo M5 administra sus propios datos mediante una base de datos MySQL.

La información perteneciente a otros módulos deberá obtenerse mediante APIs o eventos acordados entre los equipos, sin acceder directamente a sus tablas.

Esta separación respeta el principio de propiedad de datos establecido para la arquitectura distribuida del proyecto.

## 8. Estado de las decisiones

Las tecnologías mencionadas se encuentran utilizadas en la implementación inicial del módulo M5.

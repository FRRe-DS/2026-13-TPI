// Adaptador de la API de M5 para la implementación G13 (FastAPI).
//
// El flujo (e2e.js) es el mismo en G04 y G13: lo único que cambia entre los dos
// repos es este archivo, que traduce cada paso a las rutas y cuerpos de cada
// implementación y normaliza las respuestas (estados en minúscula).
//
// Variables de entorno:
//   BASE_URL  URL de M5 (por defecto http://127.0.0.1:8000)

import http from 'k6/http';

export const IMPL = 'G13';

const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const API = `${BASE_URL}/api/v1`;

// Parámetros comunes de cada request. `esperados` son los códigos HTTP que ese
// paso espera: así un 409 buscado no cuenta como error en http_req_failed.
function params(nombre, esperados, extra = {}) {
  const p = {
    headers: Object.assign({ 'Content-Type': 'application/json' }, extra),
    tags: { name: nombre, m5_impl: IMPL },
  };
  if (esperados) {
    p.responseCallback = http.expectedStatuses(...esperados);
  }
  return p;
}

function cuerpo(res) {
  try {
    return res.json();
  } catch (e) {
    return null;
  }
}

// ── Salud ───────────────────────────────────────────────────────────────────

export function salud() {
  return http.get(`${BASE_URL}/health`, params('GET /health', [200]));
}

export function listo() {
  return http.get(`${BASE_URL}/health/ready`, params('GET /health/ready', [200]));
}

// ── Pasos del flujo ─────────────────────────────────────────────────────────

// RF-5.1: solicitud inmediata. La identidad del cliente sale del token (sub).
// `token` null = sin Authorization; `idempotencyKey` null = sin el header.
export function crearSolicitud({ token, idempotencyKey, origen, destino, tipoVehiculo }, esperados) {
  const extra = {};
  if (token) extra.Authorization = `Bearer ${token}`;
  if (idempotencyKey) extra['Idempotency-Key'] = idempotencyKey;
  const body = {
    origen_latitud: origen.lat,
    origen_longitud: origen.lon,
    destino_latitud: destino.lat,
    destino_longitud: destino.lon,
    tipo_vehiculo: tipoVehiculo,
  };
  return http.post(`${API}/solicitudes`, JSON.stringify(body), params('POST /solicitudes', esperados, extra));
}

// RF-5.2: solicitud activada por una reserva de M9.
export function crearSolicitudDesdeReserva({ reservaId, clienteId, origen, destino, tipoVehiculo }, esperados) {
  const body = {
    reserva_id: reservaId,
    cliente_id: clienteId,
    origen_latitud: origen.lat,
    origen_longitud: origen.lon,
    destino_latitud: destino.lat,
    destino_longitud: destino.lon,
    tipo_vehiculo: tipoVehiculo,
  };
  return http.post(
    `${API}/solicitudes/desde-reserva`,
    JSON.stringify(body),
    params('POST /solicitudes/desde-reserva', esperados),
  );
}

export function iniciarBusqueda(solicitudId, esperados) {
  return http.post(
    `${API}/solicitudes/${solicitudId}/busqueda`,
    null,
    params('POST /solicitudes/{id}/busqueda', esperados),
  );
}

export function listarOfertas(solicitudId, esperados) {
  return http.get(`${API}/solicitudes/${solicitudId}/ofertas`, params('GET /solicitudes/{id}/ofertas', esperados));
}

export function cancelarSolicitud(solicitudId, clienteId, esperados) {
  return http.post(
    `${API}/solicitudes/${solicitudId}/cancelar`,
    JSON.stringify({ cliente_id: clienteId }),
    params('POST /solicitudes/{id}/cancelar', esperados),
  );
}

// ── Lectura normalizada de respuestas ───────────────────────────────────────

export function campo(res, nombre) {
  const b = cuerpo(res);
  return b && b[nombre] !== undefined && b[nombre] !== null ? String(b[nombre]) : null;
}

export function solicitudId(res) {
  return campo(res, 'solicitud_id');
}

// G13 mezcla 'PENDIENTE'/'CANCELADA' con 'buscando'/'sin_disponibilidad':
// se compara siempre en minúscula, que es la forma acordada en la propuesta.
export function estado(res) {
  const e = campo(res, 'estado');
  return e ? e.toLowerCase() : null;
}

export function conductores(res) {
  const b = cuerpo(res);
  return b && Array.isArray(b.conductores) ? b.conductores : null;
}

export function lista(res) {
  const b = cuerpo(res);
  return Array.isArray(b) ? b : null;
}

// E2E funcional de M5 (Solicitud y Despacho) con k6.
//
// Corre con 1 VU y 1 iteración: no es una prueba de carga sino la verificación
// de un flujo de punta a punta contra la app real (MySQL real + mocks de M1, M2,
// M4 y M8). El mismo archivo es la base de los escenarios de carga A-D del Hito 3.
//
// Uso:
//   k6 run -e BASE_URL=http://127.0.0.1:8000 -e MOCKS_URL=http://127.0.0.1:8089 \
//          -e M1_TOKEN_CLIENTE=... -e M1_TOKEN_SIN_ROL=... -e M1_CLIENTE_ID=... \
//          devops/k6/e2e.js
// (los tokens los genera devops/ci/m1_tokens_prueba.py)
//
// El mock de M4 (devops/mocks) responde según tipo_vehiculo y origen:
//   AUTO              -> 2 candidatos AUTO (ejemplo 'candidatos' del contrato)
//   MOTO              -> lista vacía, radio 9.5 km (ejemplo 'sinCandidatos')
//   origen_lat -27.0  -> 503 (M4 no disponible)

import { check, group } from 'k6';
import * as m5 from './lib/api.js';
import * as mock from './lib/mocks.js';

export const options = {
  scenarios: {
    e2e: { executor: 'shared-iterations', vus: 1, iterations: 1, maxDuration: '2m' },
  },
  thresholds: {
    // Un E2E pasa solo si pasan TODAS las verificaciones...
    checks: ['rate==1.0'],
    // ...y ninguna respuesta fue un código no esperado por el paso.
    http_req_failed: ['rate==0'],
  },
};

const TOKEN_CLIENTE = __ENV.M1_TOKEN_CLIENTE;
const TOKEN_SIN_ROL = __ENV.M1_TOKEN_SIN_ROL;
const CLIENTE_ID = __ENV.M1_CLIENTE_ID;

// Resistencia, Chaco. Cada flujo usa un origen distinto para poder identificar
// en el mock de M4 la búsqueda que disparó cada solicitud.
const DESTINO = { lat: -27.4692, lon: -58.8306 };
const ORIGEN_INMEDIATA = { lat: -27.4612, lon: -58.9867 };
const ORIGEN = { lat: -27.4512, lon: -58.9867 };
const ORIGEN_M4_CAIDO = { lat: -27.0, lon: -58.9867 };

function desdeReserva(tipoVehiculo, origen = ORIGEN) {
  const datos = {
    reservaId: crypto.randomUUID(),
    clienteId: crypto.randomUUID(),
    origen,
    destino: DESTINO,
    tipoVehiculo,
  };
  const res = m5.crearSolicitudDesdeReserva(datos, [201]);
  const ok = check(res, {
    'desde reserva: 201': (r) => r.status === 201,
    'desde reserva: devuelve solicitud_id': (r) => m5.solicitudId(r) !== null,
    'desde reserva: estado pendiente': (r) => m5.estado(r) === 'pendiente',
  });
  return ok ? Object.assign({ id: m5.solicitudId(res) }, datos) : null;
}

export function setup() {
  check(m5.salud(), { 'health: 200': (r) => r.status === 200 });
  check(m5.listo(), { 'health/ready: 200 con la base conectada': (r) => r.status === 200 });
  if (!TOKEN_CLIENTE || !TOKEN_SIN_ROL || !CLIENTE_ID) {
    throw new Error('Faltan M1_TOKEN_CLIENTE, M1_TOKEN_SIN_ROL o M1_CLIENTE_ID (ver devops/ci/m1_tokens_prueba.py)');
  }
}

export default function () {
  group('1. Solicitud inmediata (RF-5.1): M1 -> M2 -> M8 -> búsqueda en M4', () => {
    const base = { origen: ORIGEN_INMEDIATA, destino: DESTINO, tipoVehiculo: 'AUTO' };
    const clave = crypto.randomUUID();

    const sinToken = m5.crearSolicitud(Object.assign({ token: null, idempotencyKey: clave }, base), [401]);
    check(sinToken, { 'sin token: 401': (r) => r.status === 401 });

    const sinRol = m5.crearSolicitud(Object.assign({ token: TOKEN_SIN_ROL, idempotencyKey: clave }, base), [403]);
    check(sinRol, { 'token sin rol CLIENTE: 403': (r) => r.status === 403 });

    const sinClave = m5.crearSolicitud(Object.assign({ token: TOKEN_CLIENTE, idempotencyKey: null }, base), [400]);
    check(sinClave, { 'sin Idempotency-Key: 400': (r) => r.status === 400 });

    const res = m5.crearSolicitud(Object.assign({ token: TOKEN_CLIENTE, idempotencyKey: clave }, base), [201]);
    const id = m5.solicitudId(res);
    const ok = check(res, {
      'crear solicitud: 201': (r) => r.status === 201,
      'crear solicitud: estado pendiente': (r) => m5.estado(r) === 'pendiente',
      'crear solicitud: el cliente sale del token': (r) => m5.campo(r, 'cliente_id') === CLIENTE_ID,
      'crear solicitud: header Location': (r) => (r.headers.Location || '').endsWith(`/solicitudes/${id}`),
    });
    if (!ok) return;

    const repetida = m5.crearSolicitud(Object.assign({ token: TOKEN_CLIENTE, idempotencyKey: clave }, base), [200]);
    check(repetida, {
      'misma Idempotency-Key: 200 con la misma solicitud': (r) => r.status === 200 && m5.solicitudId(r) === id,
    });

    const otroCuerpo = Object.assign({}, base, { tipoVehiculo: 'MOTO' });
    const conflicto = m5.crearSolicitud(Object.assign({ token: TOKEN_CLIENTE, idempotencyKey: clave }, otroCuerpo), [409]);
    check(conflicto, { 'misma Idempotency-Key con otros datos: 409': (r) => r.status === 409 });

    // Integraciones, verificadas en el mock
    const consultasM2 = mock.contar({
      method: 'GET',
      urlPath: `/api/v1/clientes/${CLIENTE_ID}/estado-cuenta`,
    });
    check(null, { 'M2: estado de cuenta consultado una sola vez': () => consultasM2 === 1 });

    const avisosM8 = mock.esperar({
      method: 'POST',
      urlPath: '/api/v1/eventos',
      bodyPatterns: [{ contains: id }, { contains: 'VIAJE_SOLICITADO' }],
    });
    check(null, { 'M8: recibió el evento VIAJE_SOLICITADO': () => avisosM8 === 1 });

    const busquedasM4 = mock.esperar({
      method: 'GET',
      urlPath: '/api/v1/conductores/cercanos',
      queryParameters: {
        origen_latitud: { equalTo: String(ORIGEN_INMEDIATA.lat) },
        tipo_vehiculo: { equalTo: 'AUTO' },
      },
    });
    check(null, { 'M4: búsqueda de candidatos disparada sola': () => busquedasM4 >= 1 });

    const manual = m5.iniciarBusqueda(id, [409]);
    check(manual, { 'búsqueda manual sobre una ya iniciada: 409': (r) => r.status === 409 });
  });

  group('2. Solicitud desde reserva (RF-5.2) -> búsqueda de candidatos en M4 (RF-5.3)', () => {
    const s = desdeReserva('AUTO');
    if (!s) return;

    const misma = m5.crearSolicitudDesdeReserva(s, [200]);
    check(misma, {
      'misma reserva: 200 con la misma solicitud': (r) => r.status === 200 && m5.solicitudId(r) === s.id,
    });

    const busq = m5.iniciarBusqueda(s.id, [200]);
    const lista = m5.conductores(busq) || [];
    check(busq, {
      'búsqueda: 200': (r) => r.status === 200,
      'búsqueda: estado buscando': (r) => m5.estado(r) === 'buscando',
      'búsqueda: devuelve los 2 candidatos de M4': () => lista.length === 2,
      'búsqueda: solo candidatos del tipo pedido': () => lista.every((c) => c.tipo_vehiculo === 'AUTO'),
      'búsqueda: ordenados del más cercano al más lejano': () =>
        lista.every((c, i) => i === 0 || lista[i - 1].distancia_origen_km <= c.distancia_origen_km),
    });

    const repetida = m5.iniciarBusqueda(s.id, [409]);
    check(repetida, { 'búsqueda repetida: 409 (se inicia una sola vez)': (r) => r.status === 409 });

    const ofertas = m5.listarOfertas(s.id, [200]);
    check(ofertas, {
      'ofertas de la solicitud: 200': (r) => r.status === 200,
      'ofertas de la solicitud: devuelve una lista': (r) => m5.lista(r) !== null,
    });
  });

  group('3. Sin conductores disponibles -> sin_disponibilidad', () => {
    const s = desdeReserva('MOTO');
    if (!s) return;

    const busq = m5.iniciarBusqueda(s.id, [200]);
    check(busq, {
      'búsqueda sin candidatos: 200': (r) => r.status === 200,
      'búsqueda sin candidatos: estado sin_disponibilidad': (r) => m5.estado(r) === 'sin_disponibilidad',
      'búsqueda sin candidatos: lista vacía': (r) => (m5.conductores(r) || [null]).length === 0,
    });
  });

  group('4. M4 no disponible -> 503 (un error no equivale a lista vacía)', () => {
    const s = desdeReserva('AUTO', ORIGEN_M4_CAIDO);
    if (!s) return;

    const busq = m5.iniciarBusqueda(s.id, [503]);
    check(busq, { 'M4 caído: M5 responde 503': (r) => r.status === 503 });
  });

  group('5. Cancelación previa a la asignación (RF-5.7)', () => {
    const s = desdeReserva('AUTO');
    if (!s) return;

    const ajeno = m5.cancelarSolicitud(s.id, crypto.randomUUID(), [403]);
    check(ajeno, { 'cancelar solicitud ajena: 403': (r) => r.status === 403 });

    const cancel = m5.cancelarSolicitud(s.id, s.clienteId, [200]);
    check(cancel, {
      'cancelar: 200': (r) => r.status === 200,
      'cancelar: estado cancelada': (r) => m5.estado(r) === 'cancelada',
    });

    const otraVez = m5.cancelarSolicitud(s.id, s.clienteId, [409]);
    check(otraVez, { 'cancelar dos veces: 409': (r) => r.status === 409 });

    const busq = m5.iniciarBusqueda(s.id, [409]);
    check(busq, { 'buscar sobre una cancelada: 409': (r) => r.status === 409 });
  });

  // Pendiente (cuando G13 integre RF-5.5 en main): generar ofertas, dos
  // aceptaciones simultáneas y verificar que una sola gana (RNF-08).
}

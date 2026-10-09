// Lo que el E2E de UI de la revision necesita del stack vivo, por el gateway y sin navegador: la
// sesion del administrador, una lista sin revisar de un colegio ficticio y el trabajo de un acudiente
// ficticio que espera revision. El navegador solo hace lo que haria el administrador.
//
// Todas las llamadas llevan la cabecera de correlacion de la corrida (acuerdos.md §2.4). Las que hace
// el servidor de Next por su cuenta no la llevan: `ClienteApi` no la propaga.

import { randomUUID } from "node:crypto";

export const GATEWAY = process.env.TUKIT_API_URL ?? "http://127.0.0.1:8010";
export const CORRELACION = process.env.QA_CORRELACION_ID ?? randomUUID().replaceAll("-", "");
export const ANIO_LECTIVO = 2026;
export const GRADO = "Tercero";
export const ADMIN_DEMO = { correo: "admin@tukit.co", clave: "demo1234" };
// Un renglon que ningun concepto del catalogo reconoce: la resolucion lo deja en SIN_MATCH.
export const RENGLON_DESCONOCIDO = "Chaquiras de colores";

/** Una peticion al gateway. Devuelve el codigo y el cuerpo, sin lanzar por un 4xx o un 5xx. */
export async function api(metodo, ruta, { token, cuerpo } = {}) {
  const respuesta = await fetch(`${GATEWAY}${ruta}`, {
    method: metodo,
    headers: {
      "x-correlation-id": CORRELACION,
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      ...(cuerpo === undefined ? {} : { "content-type": "application/json" }),
    },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  const texto = await respuesta.text();
  let json = null;
  try {
    json = JSON.parse(texto);
  } catch {
    // El cuerpo no es JSON (un 500 en texto plano): queda en `texto`.
  }
  return { estado: respuesta.status, json, texto };
}

/** Como `api`, pero exige el codigo esperado y devuelve el JSON. */
export async function exigir(esperado, metodo, ruta, opciones) {
  const r = await api(metodo, ruta, opciones);
  if (r.estado !== esperado) {
    const cuerpo = r.texto.slice(0, 300);
    throw new Error(`${metodo} ${ruta}: se esperaba ${esperado} y llego ${r.estado}: ${cuerpo}`);
  }
  return r.json;
}

export async function abrirSesion({ correo, clave }) {
  return (await exigir(200, "POST", "/v1/sesiones", { cuerpo: { correo, clave } })).token;
}

export async function stackArriba() {
  const estado = await exigir(200, "GET", "/v1/servicios");
  if (!estado.todos_arriba) throw new Error(`el stack no esta completo: ${JSON.stringify(estado)}`);
}

/** Todos los conceptos del catalogo vivo, con su numero de productos. */
export async function conceptos() {
  const todos = [];
  for (let pagina = 1; ; pagina += 1) {
    const sobre = await exigir(200, "GET", `/v1/catalogo/conceptos?por_pagina=200&pagina=${pagina}`);
    todos.push(...sobre.conceptos);
    if (todos.length >= sobre.total || sobre.conceptos.length === 0) return todos;
  }
}

/**
 * Una lista SIN revisar para un colegio ficticio nuevo, por el destino de escritura del onboarding
 * (`POST /v1/admin/listas/importar`): los primeros conceptos de utiles con producto y un renglon que
 * nadie reconoce. Cada corrida usa su propio colegio, asi que la lista es la primera de su grado y no
 * toca las sembradas (decision N-39).
 */
export async function listaSinRevisar(tokenAdmin, cuantos = 4) {
  const conProducto = (await conceptos())
    .filter((c) => c.tipo_item === "util" && c.productos > 0)
    .sort((a, b) => a.codigo.localeCompare(b.codigo))
    .slice(0, cuantos);
  const renglones = [
    ...conProducto.map((c) => ({ texto_original: c.nombre, cantidad: 1 })),
    { texto_original: RENGLON_DESCONOCIDO, cantidad: 1 },
  ];
  const colegioId = randomUUID();
  const importada = await exigir(201, "POST", "/v1/admin/listas/importar", {
    token: tokenAdmin,
    cuerpo: {
      colegio_id: colegioId,
      grado: GRADO,
      anio_lectivo: ANIO_LECTIVO,
      items: renglones,
      evidencia: {
        documento_base64: Buffer.from("%PDF-1.4 lista ficticia de QA\n").toString("base64"),
        percepcion_cruda: [],
      },
      colegio_datos: { nombre: `Colegio Ficticio QA Admin ${colegioId.slice(0, 8)}` },
    },
  });
  return { colegioId, versionId: importada.version_id, renglones };
}

/** Registra un acudiente ficticio con un hijo en un colegio del directorio (el registro lo pide). */
export async function registrarAcudiente() {
  const directorio = await exigir(200, "GET", "/v1/colegios");
  if (!directorio.colegios.length) throw new Error("el directorio de colegios esta vacio: falta sembrarlo");
  const sufijo = randomUUID().replaceAll("-", "").slice(0, 10);
  const acudiente = { correo: `qa-admin-${sufijo}@example.test`, clave: "clave-ficticia-qa" };
  await exigir(201, "POST", "/v1/registro", {
    cuerpo: {
      ...acudiente,
      hijos: [
        { colegio_id: directorio.colegios[0].colegio_id, grado: GRADO, apodo: `QA-${sufijo.slice(0, 6)}` },
      ],
    },
  });
  const sesion = await exigir(200, "POST", "/v1/sesiones", { cuerpo: acudiente });
  return { ...acudiente, token: sesion.token, usuarioId: sesion.sesion.usuario_id };
}

/**
 * El acudiente pide el kit de ese colegio y grado. La lista no esta revisada, asi que el trabajo corre
 * el pipeline completo y espera a una persona (`espera_revision`).
 */
export async function trabajoEnRevision(tokenAcudiente, colegioId, plazoMs = 120_000) {
  const creado = await exigir(202, "POST", "/v1/trabajos", {
    token: tokenAcudiente,
    cuerpo: { hijos: [{ referencia: "hijo-1", colegio_id: colegioId, grado: GRADO }] },
  });
  const limite = Date.now() + plazoMs;
  while (Date.now() < limite) {
    const trabajo = await exigir(200, "GET", `/v1/trabajos/${creado.trabajo_id}`, { token: tokenAcudiente });
    if (["publicado", "espera_revision", "fallido"].includes(trabajo.estado)) return trabajo;
    await new Promise((listo) => setTimeout(listo, 500));
  }
  throw new Error(`el trabajo ${creado.trabajo_id} no termino en ${plazoMs / 1000} s`);
}

/** El trabajo como lo lee la consola (`GET /v1/admin/trabajos/{id}`), con sus lineas pendientes. */
export async function vistaAdmin(tokenAdmin, trabajoId) {
  return exigir(200, "GET", `/v1/admin/trabajos/${trabajoId}`, { token: tokenAdmin });
}

/** Solo los digitos de una cifra en pesos tal como la pinta la UI ("$ 12.300" -> 12300). */
export function pesos(texto) {
  return Number(String(texto).replace(/\D/g, ""));
}

/**
 * El navegador no sale de la maquina (decision N-46). Toda peticion fuera de localhost se aborta y se
 * cuenta: las de Gemini por separado (NFR-COS-01, tienen que ser cero) y el resto, que son las
 * imagenes de las tiendas, solo se anotan. El backend no tiene clave (GEMINI_API_KEY vacia), asi que
 * tampoco sale nada desde ahi.
 */
export async function guardiaDeRed(contexto) {
  const intentos = { gemini: [], externas: [] };
  await contexto.route(
    (url) => !["localhost", "127.0.0.1"].includes(url.hostname),
    (ruta) => {
      const url = ruta.request().url();
      (/generativelanguage\.googleapis\.com/.test(url) ? intentos.gemini : intentos.externas).push(url);
      return ruta.abort();
    },
  );
  return intentos;
}

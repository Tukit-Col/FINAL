// Lo que el E2E de UI del acudiente necesita del stack vivo, por el gateway y sin navegador:
// sesiones, una lista verificada de un colegio ficticio, el acudiente ficticio y el webhook firmado
// de la pasarela falsa. El navegador solo hace lo que haria el acudiente.
//
// Todas las llamadas llevan la cabecera de correlacion de la corrida (acuerdos.md §2.4). Las que hace
// el servidor de Next por su cuenta no la llevan: `ClienteApi` no la propaga.

import { createHash, randomUUID } from "node:crypto";

export const GATEWAY = process.env.TUKIT_API_URL ?? "http://127.0.0.1:8010";
export const CORRELACION = process.env.QA_CORRELACION_ID ?? randomUUID().replaceAll("-", "");
export const ANIO_LECTIVO = 2026;
export const GRADO = "Tercero";
export const ADMIN_DEMO = { correo: "admin@tukit.co", clave: "demo1234" };
export const ENTREGA_FICTICIA = {
  destinatario: "Acudiente Ficticio QA",
  direccion: "Calle Ficticia 1 # 2-3",
  ciudad: "Bogota",
};
// Secreto de eventos por omision de `PasarelaFalsa` (WOMPI_MODO=falso).
const SECRETO_EVENTOS_FALSO = "test_events_falso";

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
 * Escribe una lista SIN revisar para un colegio ficticio nuevo, por el destino de escritura del
 * onboarding (`POST /v1/admin/listas/importar`). Cada corrida usa su propio colegio, asi que la lista
 * es la primera de su grado y no toca las sembradas (decision N-39).
 */
export async function importarLista(tokenAdmin, renglones, extra = {}) {
  const colegioId = randomUUID();
  const importada = await exigir(201, "POST", "/v1/admin/listas/importar", {
    token: tokenAdmin,
    cuerpo: {
      ...extra,
      colegio_id: colegioId,
      grado: GRADO,
      anio_lectivo: ANIO_LECTIVO,
      items: renglones,
      evidencia: {
        documento_base64: Buffer.from("%PDF-1.4 lista ficticia de QA\n").toString("base64"),
        percepcion_cruda: [],
      },
      colegio_datos: { nombre: `Colegio Ficticio QA UI ${colegioId.slice(0, 8)}` },
    },
  });
  return { colegioId, versionId: importada.version_id };
}

/**
 * La lista que sube el acudiente, ya aprobada: renglones que nombran conceptos con producto, escritos
 * como `sugerencia_padre` con su `usuario_id` (lo mismo que escribe la subida despues de la
 * percepcion, decision N-45), la correccion minima del revisor (un concepto sin producto queda sin
 * concepto, como en el E2E de API, decision N-35) y el cierre de la revision. Al cerrarla, el poller
 * arma el trabajo del acudiente por la ruta rapida y lo publica.
 */
export async function listaAprobadaDelAcudiente(tokenAdmin, usuarioId, cuantos = 5) {
  const todos = await conceptos();
  const conProducto = todos
    .filter((c) => c.tipo_item === "util" && c.productos > 0)
    .sort((a, b) => a.codigo.localeCompare(b.codigo))
    .slice(0, cuantos);
  const sinProducto = new Set(todos.filter((c) => c.productos === 0).map((c) => c.codigo));
  const renglones = conProducto.map((c, i) => ({ texto_original: c.nombre, cantidad: i === 0 ? 2 : 1 }));
  const { colegioId, versionId } = await importarLista(tokenAdmin, renglones, {
    origen: "sugerencia_padre",
    contacto_referencia: usuarioId,
  });

  const revision = await exigir(200, "GET", `/v1/admin/listas/${versionId}/revision`, { token: tokenAdmin });
  for (const item of revision.items) {
    if (sinProducto.has(item.concepto?.codigo)) {
      await exigir(200, "PATCH", `/v1/admin/listas/${versionId}/items/${item.item_id}`, {
        token: tokenAdmin,
        cuerpo: { concepto_codigo: null, requiere_revision: true },
      });
    }
  }
  const cerrada = await exigir(200, "POST", `/v1/admin/listas/${versionId}/cerrar`, { token: tokenAdmin });
  if (cerrada.revisada !== true) throw new Error(`la lista ${versionId} no quedo revisada`);
  return { colegioId, versionId, renglones };
}

/** Registra un acudiente ficticio con un hijo en un colegio del directorio (el registro lo pide). */
export async function registrarAcudiente() {
  const directorio = await exigir(200, "GET", "/v1/colegios");
  if (!directorio.colegios.length) throw new Error("el directorio de colegios esta vacio: falta sembrarlo");
  const sufijo = randomUUID().replaceAll("-", "").slice(0, 10);
  const acudiente = { correo: `qa-ui-${sufijo}@example.test`, clave: "clave-ficticia-qa" };
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

/** Espera a que el poller arme el trabajo de esa version para el acudiente y lo deje terminado. */
export async function trabajoDelAcudiente(token, versionId, plazoMs = 120_000) {
  const limite = Date.now() + plazoMs;
  while (Date.now() < limite) {
    const mios = await exigir(200, "GET", "/v1/trabajos", { token });
    const suyo = mios.trabajos.find((t) => t.hijos.some((h) => h.version_id === versionId));
    if (suyo && ["publicado", "espera_revision", "fallido"].includes(suyo.estado)) {
      return exigir(200, "GET", `/v1/trabajos/${suyo.trabajo_id}`, { token });
    }
    await new Promise((listo) => setTimeout(listo, 500));
  }
  throw new Error(`el poller no armo el trabajo de la version ${versionId} en ${plazoMs / 1000} s`);
}

/** El webhook APPROVED con la misma forma y firma que `PasarelaFalsa.emitir_evento`. */
export function eventoAprobado(referencia, transaccion) {
  const timestamp = 1_700_000_000;
  const checksum = createHash("sha256")
    .update(`${transaccion}APPROVED${timestamp}${SECRETO_EVENTOS_FALSO}`)
    .digest("hex");
  return {
    id: `evt-${transaccion}`,
    event: "transaction.updated",
    timestamp,
    data: { transaction: { id: transaccion, reference: referencia, status: "APPROVED", amount_in_cents: 0 } },
    signature: { properties: ["transaction.id", "transaction.status"], checksum },
  };
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

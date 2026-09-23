// El lado del navegador de las acciones de la SPA de catálogo (P4c).
//
// Igual que `api-navegador.ts`: habla solo con los Route Handlers de esta
// misma app (`/api/catalogo/**`), nunca con el backend. La URL del backend y
// el token se quedan en el servidor. Módulo propio del slice para no pisar
// `api-navegador.ts`, que otro slice puede tocar.

import type {
  AltaLibro,
  AltaUtil,
  AprobarPropuesta,
  CandidatoTienda,
  ErrorApi,
  FiltrosProductos,
  PaginaProductos,
  ProductoCatalogoDetalle,
  ProductoEditable,
  PropuestaCola,
  PropuestaEncolada,
  RechazarPropuesta,
} from "@tukit/contrato";

export class FalloCatalogo extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
    this.name = "FalloCatalogo";
  }
}

async function pedir<T>(ruta: string, init: RequestInit): Promise<T> {
  const respuesta = await fetch(ruta, init);
  const texto = await respuesta.text();
  const leido: unknown = texto ? JSON.parse(texto) : null;

  if (!respuesta.ok) {
    const error = (leido ?? {}) as ErrorApi & Record<string, unknown>;
    // El mensaje que se muestra es el del backend, no uno inventado aquí: es
    // el único que sabe por qué rechazó (campo_no_editable, nivel_invalido,
    // empaque_invalido, concepto_no_existe…).
    throw new FalloCatalogo(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "Algo salió mal al guardar el cambio.",
      error,
    );
  }
  return leido as T;
}

const id = encodeURIComponent;

/** GET paginado con filtros. El querystring se arma solo con lo que vino. */
export function buscarProductos(filtros: FiltrosProductos): Promise<PaginaProductos> {
  const qs = new URLSearchParams();
  if (filtros.busqueda?.trim()) qs.set("busqueda", filtros.busqueda.trim());
  if (filtros.concepto) qs.set("concepto", filtros.concepto);
  if (filtros.nivel) qs.set("nivel", filtros.nivel);
  if (filtros.personaje) qs.set("personaje", filtros.personaje);
  if (filtros.con_personaje !== undefined) qs.set("con_personaje", String(filtros.con_personaje));
  if (filtros.con_precio !== undefined) qs.set("con_precio", String(filtros.con_precio));
  if (filtros.con_ofertas !== undefined) qs.set("con_ofertas", String(filtros.con_ofertas));
  if (filtros.pagina !== undefined) qs.set("pagina", String(filtros.pagina));
  if (filtros.por_pagina !== undefined) qs.set("por_pagina", String(filtros.por_pagina));
  const cadena = qs.toString();
  return pedir<PaginaProductos>(`/api/catalogo/productos${cadena ? `?${cadena}` : ""}`, {
    method: "GET",
  });
}

/** PATCH — CRUD de todos los campos y la re-etiqueta (nivel/personaje/marca). */
export function editarProducto(
  sku: string,
  cambios: ProductoEditable,
): Promise<ProductoCatalogoDetalle> {
  return pedir<ProductoCatalogoDetalle>(`/api/catalogo/productos/${id(sku)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cambios),
  });
}

/** POST — mueve el producto bajo otro concepto (dispara re-embedding). */
export function reclasificarProducto(
  sku: string,
  concepto: string,
): Promise<ProductoCatalogoDetalle> {
  return pedir<ProductoCatalogoDetalle>(`/api/catalogo/productos/${id(sku)}/reclasificar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ concepto }),
  });
}

/** DELETE — baja suave (activo=False en el backend), 204 sin cuerpo. */
export function eliminarProducto(sku: string): Promise<void> {
  return pedir<void>(`/api/catalogo/productos/${id(sku)}`, { method: "DELETE" });
}

// --------------------------------------------------- Curaduría proactiva (P4c bis)
//
// La cola de propuestas y las altas de útil/libro. Curaduría del catálogo ANTES
// de que un acudiente pregunte, distinta de la revisión de listas de colegio.
// Encolar y aprobar son dos pasos separados: `altaUtil`/`altaLibro` meten la
// propuesta en la cola; `aprobarPropuesta`/`rechazarPropuesta` la cierran.

/** GET — la cola de pendientes, opcionalmente filtrada por concepto. */
export function colaPropuestas(concepto?: string): Promise<PropuestaCola[]> {
  const qs = concepto ? `?concepto=${id(concepto)}` : "";
  return pedir<PropuestaCola[]>(`/api/catalogo/propuestas${qs}`, { method: "GET" });
}

/** GET — candidatos en vivo de una tienda (VTEX/Shopify) para el alta de útil. */
export function buscarEnTienda(
  slug: string,
  consulta: string,
  cuantos?: number,
): Promise<CandidatoTienda[]> {
  const qs = new URLSearchParams({ consulta });
  if (cuantos !== undefined) qs.set("cuantos", String(cuantos));
  return pedir<CandidatoTienda[]>(
    `/api/catalogo/tiendas/${id(slug)}/buscar?${qs.toString()}`,
    { method: "GET" },
  );
}

/** POST — encola un útil elegido de la tienda (no aprueba: cae en la cola). */
export function altaUtil(cuerpo: AltaUtil): Promise<PropuestaEncolada> {
  return pedir<PropuestaEncolada>(`/api/catalogo/propuestas/util`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
}

/** POST — encola un libro por ISBN (manual, precio en pesos > 0). */
export function altaLibro(cuerpo: AltaLibro): Promise<PropuestaEncolada> {
  return pedir<PropuestaEncolada>(`/api/catalogo/propuestas/libro`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
}

/** POST — aprueba una propuesta de la cola (nace producto + oferta + precio). */
export function aprobarPropuesta(
  propuestaId: string,
  cuerpo: AprobarPropuesta,
): Promise<{ id: string; estado: string }> {
  return pedir<{ id: string; estado: string }>(
    `/api/catalogo/propuestas/${id(propuestaId)}/aprobar`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    },
  );
}

/** POST — rechaza una propuesta (con motivo y, opcional, `no_surtir`). */
export function rechazarPropuesta(
  propuestaId: string,
  cuerpo: RechazarPropuesta,
): Promise<{ id: string; estado: string }> {
  return pedir<{ id: string; estado: string }>(
    `/api/catalogo/propuestas/${id(propuestaId)}/rechazar`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    },
  );
}

// El lado del navegador de las acciones de la SPA de catálogo (P4c).
//
// Igual que `api-navegador.ts`: habla solo con los Route Handlers de esta
// misma app (`/api/catalogo/**`), nunca con el backend. La URL del backend y
// el token se quedan en el servidor. Módulo propio del slice para no pisar
// `api-navegador.ts`, que otro slice puede tocar.

import type {
  ErrorApi,
  FiltrosProductos,
  PaginaProductos,
  ProductoCatalogoDetalle,
  ProductoEditable,
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

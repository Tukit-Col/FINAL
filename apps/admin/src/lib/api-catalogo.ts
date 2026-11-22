import type {
  AltaLibro,
  AltaUtil,
  AltaUtilManual,
  AprobarPropuesta,
  CandidatoTienda,
  ConceptoCreado,
  CrearConcepto,
  ErrorApi,
  FiltrosProductos,
  PaginaProductos,
  ProductoCatalogoDetalle,
  ProductoEditable,
  PropuestaCola,
  PropuestaEncolada,
  RechazarPropuesta,
} from "@tukit/contrato";
import { conEspera } from "@tukit/contrato";

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
    const error = conEspera(
      respuesta.status,
      (leido ?? {}) as ErrorApi & Record<string, unknown>,
      respuesta.headers.get("Retry-After"),
    );
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

export function eliminarProducto(sku: string): Promise<void> {
  return pedir<void>(`/api/catalogo/productos/${id(sku)}`, { method: "DELETE" });
}

export function colaPropuestas(concepto?: string): Promise<PropuestaCola[]> {
  const qs = concepto ? `?concepto=${id(concepto)}` : "";
  return pedir<PropuestaCola[]>(`/api/catalogo/propuestas${qs}`, { method: "GET" });
}

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

export function crearConcepto(cuerpo: CrearConcepto): Promise<ConceptoCreado> {
  return pedir<ConceptoCreado>(`/api/catalogo/conceptos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
}

export function altaUtil(cuerpo: AltaUtil): Promise<PropuestaEncolada> {
  return pedir<PropuestaEncolada>(`/api/catalogo/propuestas/util`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
}

export function altaUtilManual(cuerpo: AltaUtilManual): Promise<PropuestaEncolada> {
  return pedir<PropuestaEncolada>(`/api/catalogo/propuestas/util-manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
}

export function altaLibro(cuerpo: AltaLibro): Promise<PropuestaEncolada> {
  return pedir<PropuestaEncolada>(`/api/catalogo/propuestas/libro`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
}

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

// El lado del navegador de las acciones del §7.
//
// Habla solo con los Route Handlers de esta misma app, nunca con el backend:
// la URL del backend y la bandera `TUKIT_ORIGEN_DATOS` se quedan en el
// servidor y el navegador no tiene que saber que existen.

import type {
  AltaProducto,
  DecisionRevision,
  ErrorApi,
  MarcarNoDisponible,
  ProductoDadoDeAlta,
  SinCoincidencia,
  ValidarLinea,
} from "@tukit/contrato";

export class FalloApi extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
    this.name = "FalloApi";
  }
}

async function enviar<T>(ruta: string, cuerpo: unknown): Promise<T> {
  const respuesta = await fetch(ruta, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  const texto = await respuesta.text();
  const leido: unknown = texto ? JSON.parse(texto) : null;

  if (!respuesta.ok) {
    const error = (leido ?? {}) as ErrorApi & Record<string, unknown>;
    // El mensaje que se muestra es el del backend, no uno inventado aqui: es
    // el unico que sabe por que rechazo la accion (motivo vacio, precio con
    // decimales, trabajo ya publicado).
    throw new FalloApi(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "Algo salio mal al guardar el cambio.",
      error,
    );
  }
  return leido as T;
}

const id = encodeURIComponent;

/** AD-02. Sin `sku` se lee como "confirmo el producto que el sistema eligio". */
export function validarLinea(
  trabajoId: string,
  itemId: string,
  cuerpo: ValidarLinea,
): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/lineas/${id(itemId)}/validar`, cuerpo);
}

/** AD-02. El motivo es obligatorio: una marca sin motivo no se puede revisar despues. */
export function marcarSinCoincidencia(
  trabajoId: string,
  itemId: string,
  cuerpo: SinCoincidencia,
): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/lineas/${id(itemId)}/sin-coincidencia`, cuerpo);
}

/** AD-07. Alta manual con precio e imagen, para utiles y libros. */
export function altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta> {
  return enviar<ProductoDadoDeAlta>("/api/productos", cuerpo);
}

/** AD-05. Apaga la oferta en catalogo, o sea para todos los trabajos. */
export function marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void> {
  return enviar(`/api/productos/${id(sku)}/no-disponible`, cuerpo);
}

/** AD-06. Aprobar publica y avisa al acudiente; devolver reabre en silencio. */
export function decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/revision`, cuerpo);
}

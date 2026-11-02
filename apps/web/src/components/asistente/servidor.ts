// Puente servidor del asistente: reenvia al backend con el token de la sesion
// y devuelve solo lo que el navegador puede pintar.
//
// El navegador no conoce la URL del backend ni el token. Si el asistente falla
// por cualquier causa se responde 503 `asistente_no_disponible`, que es la senal
// para caer al formulario de siempre.

import { origenDeDatos, urlApi } from "@tukit/contrato/servidor";
import { tokenDeSesion } from "@/lib/sesion";
import { validarEspec, type EspecUi } from "./espec";

const ESPERA_MS = 20_000;

export interface Resultado {
  estado: number;
  cuerpo: Record<string, unknown>;
}

export const NO_DISPONIBLE: Resultado = {
  estado: 503,
  cuerpo: {
    error: "asistente_no_disponible",
    mensaje: "El asistente no está disponible ahora. Puedes llenar el formulario como siempre.",
  },
};

export async function reenviar(ruta: string, cuerpo: unknown): Promise<Resultado> {
  const token = await tokenDeSesion();
  let respuesta: Response;
  try {
    respuesta = await fetch(`${urlApi()}${ruta}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(cuerpo),
      signal: AbortSignal.timeout(ESPERA_MS),
      cache: "no-store",
    });
  } catch {
    return NO_DISPONIBLE;
  }
  let json: unknown = null;
  try {
    json = await respuesta.json();
  } catch {
    json = null;
  }
  if (typeof json !== "object" || json === null || Array.isArray(json)) {
    return respuesta.ok ? NO_DISPONIBLE : { estado: respuesta.status, cuerpo: { error: "error_desconocido" } };
  }
  const objeto = json as Record<string, unknown>;
  // Un fallo del modelo o un 404 de bandera apagada se leen igual en la web: sin asistente.
  if (respuesta.status === 503 || (respuesta.status === 404 && objeto["error"] === "asistente_desactivado")) {
    return NO_DISPONIBLE;
  }
  return { estado: respuesta.status, cuerpo: objeto };
}

/** La spec validada o `null`: lo que no pasa la lista blanca no llega al navegador. */
export function especSegura(v: unknown): EspecUi | null {
  return validarEspec(v);
}

/** Una foto real del catalogo para un personaje; `null` si no hay (la tarjeta cae al icono). */
export async function imagenDePersonaje(nombre: string): Promise<string | null> {
  try {
    const pagina = await origenDeDatos().buscarProductos({
      personaje: nombre,
      con_precio: true,
      por_pagina: 12,
    });
    for (const producto of pagina.productos) {
      const url = producto.imagen_url;
      if (typeof url !== "string") continue;
      try {
        if (new URL(url).protocol === "https:") return url;
      } catch {
        /* siguiente producto */
      }
    }
  } catch {
    /* sin foto, se pinta el icono */
  }
  return null;
}

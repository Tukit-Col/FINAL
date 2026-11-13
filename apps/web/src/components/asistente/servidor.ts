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

/** Apagado en este entorno (bandera del servidor): distinto de "fallo", la web lo dice con otras palabras. */
export const DESACTIVADO: Resultado = {
  estado: 503,
  cuerpo: {
    error: "asistente_desactivado",
    mensaje: "El asistente no está activo en este entorno.",
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
  // Bandera apagada (404 del backend) y fallo del modelo (503) se distinguen: una es "no esta
  // activo aqui", la otra "ahora fallo, intenta de nuevo".
  if (respuesta.status === 404 && objeto["error"] === "asistente_desactivado") return DESACTIVADO;
  if (respuesta.status === 503) return NO_DISPONIBLE;
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

/** Estado del asistente para el panel: sin llamar al modelo. `caido` si el backend no contesta. */
export async function estadoDelAsistente(): Promise<"activo" | "apagado" | "sin_modelo" | "caido"> {
  try {
    const r = await fetch(`${urlApi()}/v1/nl2c/estado`, {
      signal: AbortSignal.timeout(4_000),
      cache: "no-store",
    });
    if (!r.ok) return r.status === 404 ? "apagado" : "caido";
    const j = (await r.json()) as { activo?: unknown; modelo_configurado?: unknown };
    if (j.activo !== true) return "apagado";
    return j.modelo_configurado === false ? "sin_modelo" : "activo";
  } catch {
    return "caido";
  }
}
